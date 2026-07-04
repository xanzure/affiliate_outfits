from __future__ import annotations

import sqlite3
import json
from dataclasses import dataclass
from typing import Any
from urllib.request import Request, urlopen

from app.db.models import Post
from app.db.posts import create_post
from app.config import Settings, load_settings


TIKTOK_PHOTO_POST_URL = "https://open.tiktokapis.com/v2/post/publish/content/init/"


@dataclass(frozen=True)
class TikTokPublishResult:
    publish_id: str
    raw_response: dict[str, Any]


class TikTokApiClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or load_settings()
        if not self.settings.tiktok_access_token:
            raise ValueError("TIKTOK_ACCESS_TOKEN is required for TikTok autoposting")

    def publish_photo_slideshow(
        self,
        *,
        image_urls: list[str],
        caption: str,
        title: str | None = None,
    ) -> TikTokPublishResult:
        if not image_urls:
            raise ValueError("TikTok photo post requires at least one image URL")
        if len(image_urls) > 35:
            raise ValueError("TikTok photo post supports at most 35 image URLs")

        post_info: dict[str, Any] = {
            "title": _utf16_trim(title or caption, 90),
            "description": _utf16_trim(caption, 4000),
        }
        if self.settings.tiktok_post_mode == "DIRECT_POST":
            post_info.update(
                {
                    "privacy_level": self.settings.tiktok_privacy_level,
                    "disable_comment": self.settings.tiktok_disable_comment,
                    "auto_add_music": self.settings.tiktok_auto_add_music,
                    "brand_content_toggle": self.settings.tiktok_brand_content_toggle,
                    "brand_organic_toggle": self.settings.tiktok_brand_organic_toggle,
                }
            )

        payload = {
            "post_info": post_info,
            "source_info": {
                "source": "PULL_FROM_URL",
                "photo_cover_index": 0,
                "photo_images": image_urls,
            },
            "post_mode": self.settings.tiktok_post_mode,
            "media_type": "PHOTO",
        }
        response = _post_json(
            TIKTOK_PHOTO_POST_URL,
            payload,
            bearer_token=self.settings.tiktok_access_token or "",
        )
        error = response.get("error", {})
        if isinstance(error, dict) and error.get("code") not in {None, "ok"}:
            raise RuntimeError(f"TikTok publish failed: {error.get('code')} {error.get('message', '')}")

        data = response.get("data", {})
        publish_id = data.get("publish_id") if isinstance(data, dict) else None
        if not isinstance(publish_id, str) or not publish_id:
            raise RuntimeError("TikTok publish response did not include data.publish_id")
        return TikTokPublishResult(publish_id=publish_id, raw_response=response)


def create_local_tiktok_post(
    conn: sqlite3.Connection,
    *,
    concept_id: str | None = None,
    outfit_id: str | None,
    image_path: str,
    caption: str,
    hashtags: list[str],
    music_category: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Post:
    return create_post(
        conn,
        platform="tiktok",
        concept_id=concept_id,
        outfit_id=outfit_id,
        image_path=image_path,
        caption=_caption_with_hashtags(caption, hashtags),
        status="draft",
        metadata={
            "local_only": True,
            "api_posting_enabled": False,
            "hashtags": hashtags,
            "music_category": music_category,
            **(metadata or {}),
        },
    )


def create_local_tiktok_slideshow_post(
    conn: sqlite3.Connection,
    *,
    concept_id: str | None = None,
    outfit_ids: list[str],
    image_paths: list[str],
    caption: str,
    hashtags: list[str],
    music_category: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Post:
    if not outfit_ids:
        raise ValueError("TikTok slideshow must include at least one outfit")
    if len(outfit_ids) != len(image_paths):
        raise ValueError("TikTok slideshow outfit_ids and image_paths must have the same length")

    return create_post(
        conn,
        platform="tiktok",
        concept_id=concept_id,
        outfit_id=outfit_ids[0],
        image_path=image_paths[0],
        caption=_caption_with_hashtags(caption, hashtags),
        status="draft",
        metadata={
            "local_only": True,
            "api_posting_enabled": False,
            "post_format": "slideshow",
            "outfit_ids": outfit_ids,
            "image_paths": image_paths,
            "hashtags": hashtags,
            "music_category": music_category,
            **(metadata or {}),
        },
    )


def _caption_with_hashtags(caption: str, hashtags: list[str]) -> str:
    cleaned_tags = [tag if tag.startswith("#") else f"#{tag}" for tag in hashtags]
    suffix = " ".join(cleaned_tags)
    return f"{caption.strip()} {suffix}".strip()


def _post_json(url: str, payload: dict[str, Any], *, bearer_token: str) -> dict[str, Any]:
    from urllib.error import HTTPError

    body = json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json; charset=UTF-8",
            "User-Agent": "affiliate-outfits/0.1",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        # urllib's HTTPError str() is just "HTTP Error 401: Unauthorized" — the
        # useful detail (e.g. "access_token_invalid") is in the response body.
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"TikTok API HTTP {exc.code}: {detail}") from exc


def _utf16_trim(value: str, max_units: int) -> str:
    output = ""
    units = 0
    for char in value.strip():
        char_units = len(char.encode("utf-16-le")) // 2
        if units + char_units > max_units:
            break
        output += char
        units += char_units
    return output
