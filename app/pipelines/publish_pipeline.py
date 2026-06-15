from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from app.config import Settings, load_settings
from app.db._helpers import EST, est_today
from app.db.models import Outfit, Post, Product
from app.db.posts import list_posts, update_post_metadata, update_post_status
from app.services.pinterest_service import PinterestApiClient, create_local_pinterest_post
from app.services.tiktok_service import TikTokApiClient, create_local_tiktok_post, create_local_tiktok_slideshow_post


@dataclass(frozen=True)
class LocalPublishResult:
    posts: list[Post]


@dataclass(frozen=True)
class AutoPublishResult:
    published: list[Post]
    failed: list[Post]
    skipped: list[Post]


def create_local_publish_records(
    conn: sqlite3.Connection,
    *,
    concept_id: str | None = None,
    outfit: Outfit,
    products: list[Product],
    collage_path: Path,
    engagement_output: dict[str, Any],
) -> LocalPublishResult:
    _validate_engagement_output(engagement_output)
    tiktok = engagement_output["tiktok"]
    pinterest = engagement_output["pinterest"]

    shared_metadata = {
        "product_ids": [product.id for product in products],
        "product_urls": [product.affiliate_url or product.url for product in products],
        "affiliate_urls": [product.affiliate_url for product in products if product.affiliate_url],
        "engagement_notes": engagement_output.get("notes", []),
    }

    posts = [
        create_local_tiktok_post(
            conn,
            concept_id=concept_id,
            outfit_id=outfit.id,
            image_path=str(collage_path),
            caption=tiktok["caption"],
            hashtags=tiktok["hashtags"],
            music_category=tiktok.get("music_category"),
            metadata=shared_metadata,
        ),
        create_local_pinterest_post(
            conn,
            concept_id=concept_id,
            outfit_id=outfit.id,
            image_path=str(collage_path),
            title=pinterest["title"],
            description=pinterest["description"],
            hashtags=pinterest["hashtags"],
            metadata=shared_metadata,
        ),
    ]

    return LocalPublishResult(posts=posts)


def create_local_publish_records_for_outfit_set(
    conn: sqlite3.Connection,
    *,
    concept_id: str | None = None,
    outfits: list[Outfit],
    products_by_outfit: list[list[Product]],
    collage_paths: list[Path],
    engagement_output: dict[str, Any],
    schedule_date_est: str | None = None,
    pinterest_spacing_hours: int = 2,
) -> LocalPublishResult:
    if not outfits:
        raise ValueError("publish set must include at least one outfit")
    if len(outfits) != len(products_by_outfit) or len(outfits) != len(collage_paths):
        raise ValueError("outfits, products_by_outfit, and collage_paths must have the same length")

    _validate_engagement_output_for_outfit_set(engagement_output, outfit_count=len(outfits))
    tiktok = engagement_output["tiktok"]
    pinterest_posts = _pinterest_entries(engagement_output, outfit_count=len(outfits))

    all_products = [product for products in products_by_outfit for product in products]
    shared_metadata = {
        "content_unit": "daily_concept_outfit_set",
        "outfit_count": len(outfits),
        "product_ids": [product.id for product in all_products],
        "product_urls": [product.affiliate_url or product.url for product in all_products],
        "affiliate_urls": [product.affiliate_url for product in all_products if product.affiliate_url],
        "engagement_notes": engagement_output.get("notes", []),
    }

    posts: list[Post] = [
        create_local_tiktok_slideshow_post(
            conn,
            concept_id=concept_id,
            outfit_ids=[outfit.id for outfit in outfits],
            image_paths=[str(path) for path in collage_paths],
            caption=tiktok["caption"],
            hashtags=tiktok["hashtags"],
            music_category=tiktok.get("music_category"),
            metadata=shared_metadata,
        )
    ]

    schedule_times = pinterest_schedule_times(
        count=len(outfits),
        schedule_date_est=schedule_date_est,
        spacing_hours=pinterest_spacing_hours,
    )
    for index, (outfit, products, collage_path, pinterest, scheduled_at) in enumerate(
        zip(outfits, products_by_outfit, collage_paths, pinterest_posts, schedule_times, strict=True),
        start=1,
    ):
        posts.append(
            create_local_pinterest_post(
                conn,
                concept_id=concept_id,
                outfit_id=outfit.id,
                image_path=str(collage_path),
                title=pinterest["title"],
                description=pinterest["description"],
                hashtags=pinterest["hashtags"],
                status="scheduled",
                scheduled_at=scheduled_at,
                metadata={
                    **shared_metadata,
                    "outfit_set_index": index,
                    "product_ids": [product.id for product in products],
                    "product_urls": [product.affiliate_url or product.url for product in products],
                    "affiliate_urls": [
                        product.affiliate_url for product in products if product.affiliate_url
                    ],
                },
            )
        )

    return LocalPublishResult(posts=posts)


def autopublish_posts(
    conn: sqlite3.Connection,
    posts: list[Post],
    *,
    settings: Settings | None = None,
    now: datetime | None = None,
    tiktok_client: TikTokApiClient | None = None,
    pinterest_client: PinterestApiClient | None = None,
) -> AutoPublishResult:
    settings = settings or load_settings()
    if not settings.autoposting_enabled:
        return AutoPublishResult(published=[], failed=[], skipped=posts)

    now = now or datetime.now(UTC)
    published: list[Post] = []
    failed: list[Post] = []
    skipped: list[Post] = []

    for post in posts:
        if post.status == "published":
            skipped.append(post)
            continue
        if post.status == "scheduled" and not _post_is_due(post, now):
            skipped.append(post)
            continue

        try:
            if post.platform == "tiktok":
                result_id, raw_response = _publish_tiktok_post(
                    post,
                    settings=settings,
                    client=tiktok_client or TikTokApiClient(settings),
                )
            elif post.platform == "pinterest":
                result_id, raw_response = _publish_pinterest_post(
                    post,
                    settings=settings,
                    client=pinterest_client or PinterestApiClient(settings),
                )
            else:
                skipped.append(post)
                continue

            update_post_metadata(
                conn,
                post.id,
                {
                    "local_only": False,
                    "api_posting_enabled": True,
                    "api_response": raw_response,
                },
            )
            published.append(
                update_post_status(
                    conn,
                    post.id,
                    status="published",
                    platform_post_id=result_id,
                    published_at=now.astimezone(UTC).isoformat(timespec="seconds"),
                )
            )
        except Exception as exc:
            update_post_metadata(
                conn,
                post.id,
                {
                    "api_posting_enabled": True,
                    "api_error": str(exc),
                },
            )
            failed.append(update_post_status(conn, post.id, status="failed"))

    return AutoPublishResult(published=published, failed=failed, skipped=skipped)


def autopublish_due_posts(
    conn: sqlite3.Connection,
    *,
    settings: Settings | None = None,
    now: datetime | None = None,
    tiktok_client: TikTokApiClient | None = None,
    pinterest_client: PinterestApiClient | None = None,
) -> AutoPublishResult:
    candidates = [
        post
        for post in list_posts(conn)
        if post.platform in {"tiktok", "pinterest"} and post.status in {"draft", "scheduled"}
    ]
    return autopublish_posts(
        conn,
        candidates,
        settings=settings,
        now=now,
        tiktok_client=tiktok_client,
        pinterest_client=pinterest_client,
    )


def pinterest_schedule_times(
    *,
    count: int,
    schedule_date_est: str | None = None,
    spacing_hours: int = 2,
    start_hour: int = 10,
) -> list[str]:
    if count < 1:
        raise ValueError("Pinterest schedule count must be at least 1")
    if spacing_hours < 1:
        raise ValueError("Pinterest spacing must be at least 1 hour")

    schedule_date = date.fromisoformat(schedule_date_est or est_today())
    start = datetime.combine(schedule_date, time(hour=start_hour), tzinfo=EST)
    return [
        (start + timedelta(hours=spacing_hours * index)).isoformat(timespec="minutes")
        for index in range(count)
    ]


def _publish_tiktok_post(
    post: Post,
    *,
    settings: Settings,
    client: TikTokApiClient,
) -> tuple[str, dict[str, Any]]:
    image_paths = post.metadata.get("image_paths")
    if not isinstance(image_paths, list):
        image_paths = [post.image_path]
    image_urls = [
        _public_asset_url(str(path), settings=settings)
        for path in image_paths
        if isinstance(path, str) and path
    ]
    result = client.publish_photo_slideshow(
        image_urls=image_urls,
        caption=post.caption or "",
        title=post.caption or "Outfit slideshow",
    )
    return result.publish_id, result.raw_response


def _publish_pinterest_post(
    post: Post,
    *,
    settings: Settings,
    client: PinterestApiClient,
) -> tuple[str, dict[str, Any]]:
    if not post.image_path:
        raise ValueError("Pinterest post is missing image_path")
    product_urls = post.metadata.get("product_urls", [])
    link = product_urls[0] if isinstance(product_urls, list) and product_urls else None
    result = client.create_pin(
        image_url=_public_asset_url(post.image_path, settings=settings),
        title=str(post.metadata.get("title") or "Outfit"),
        description=post.caption or "",
        link=link if isinstance(link, str) else None,
    )
    return result.pin_id, result.raw_response


def _public_asset_url(path: str, *, settings: Settings) -> str:
    if path.startswith(("http://", "https://")):
        return path
    if not settings.public_asset_base_url:
        raise ValueError("PUBLIC_ASSET_BASE_URL is required for autoposting local assets")
    return f"{settings.public_asset_base_url}/{path.lstrip('/')}"


def _post_is_due(post: Post, now: datetime) -> bool:
    if not post.published_at:
        return True
    scheduled_at = datetime.fromisoformat(post.published_at)
    if scheduled_at.tzinfo is None:
        scheduled_at = scheduled_at.replace(tzinfo=EST)
    return scheduled_at <= now.astimezone(scheduled_at.tzinfo)


def _validate_engagement_output(output: dict[str, Any]) -> None:
    if not isinstance(output, dict):
        raise ValueError("engagement output must be a JSON object")

    for platform in ("tiktok", "pinterest"):
        if not isinstance(output.get(platform), dict):
            raise ValueError(f"engagement output must include object '{platform}'")

    tiktok = output["tiktok"]
    pinterest = output["pinterest"]
    _require_string(tiktok, "caption", "tiktok")
    _require_list(tiktok, "hashtags", "tiktok")
    _require_string(pinterest, "title", "pinterest")
    _require_string(pinterest, "description", "pinterest")
    _require_list(pinterest, "hashtags", "pinterest")


def _validate_engagement_output_for_outfit_set(output: dict[str, Any], *, outfit_count: int) -> None:
    if not isinstance(output, dict):
        raise ValueError("engagement output must be a JSON object")
    if not isinstance(output.get("tiktok"), dict):
        raise ValueError("engagement output must include object 'tiktok'")

    tiktok = output["tiktok"]
    _require_string(tiktok, "caption", "tiktok")
    _require_list(tiktok, "hashtags", "tiktok")

    pinterest_posts = _pinterest_entries(output, outfit_count=outfit_count)
    for index, entry in enumerate(pinterest_posts):
        parent = f"pinterest_posts[{index}]"
        _require_string(entry, "title", parent)
        _require_string(entry, "description", parent)
        _require_list(entry, "hashtags", parent)


def _pinterest_entries(output: dict[str, Any], *, outfit_count: int) -> list[dict[str, Any]]:
    entries = output.get("pinterest_posts")
    if entries is None:
        single = output.get("pinterest")
        if not isinstance(single, dict):
            raise ValueError("engagement output must include 'pinterest_posts' or 'pinterest'")
        return [single for _ in range(outfit_count)]

    if not isinstance(entries, list):
        raise ValueError("engagement output field 'pinterest_posts' must be a list")
    if len(entries) != outfit_count:
        raise ValueError(
            f"engagement output must include exactly {outfit_count} pinterest_posts; got {len(entries)}"
        )
    if not all(isinstance(entry, dict) for entry in entries):
        raise ValueError("engagement output field 'pinterest_posts' must contain objects")
    return entries


def _require_string(value: dict[str, Any], field: str, parent: str) -> None:
    if not isinstance(value.get(field), str) or not value[field].strip():
        raise ValueError(f"engagement output field '{parent}.{field}' must be a non-empty string")


def _require_list(value: dict[str, Any], field: str, parent: str) -> None:
    items = value.get(field)
    if not isinstance(items, list) or not all(isinstance(item, str) for item in items):
        raise ValueError(f"engagement output field '{parent}.{field}' must be a list of strings")
