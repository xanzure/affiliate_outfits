from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _step(msg: str, index: int | None = None, total: int | None = None) -> None:
    prefix = f"[{index}/{total}] " if index is not None else "── "
    print(f"\n{prefix}{msg}", flush=True)

from app.agents.collage.style_agent import BatchVisualStyle, generate_batch_visual_style
from app.agents.outfit.parser import normalize_outfit_agent_output, normalize_outfit_agent_outputs
from app.agents.engagement.agent import generate_engagement_with_llm
from app.agents.outfit.agent import generate_outfit_batch_with_llm, generate_outfit_with_llm, curate_outfit_products_with_feedback
from app.agents.outfit.curator import outfit_spec_to_pipeline_format
from app.config import Settings, load_settings
from app.db.collages import create_collage
from app.db.concepts import get_concept, update_concept_metadata
from app.db.models import Outfit, Product
from app.db.outfits import create_outfit, update_outfit_spec
from app.pipelines.collage_pipeline import render_html_collage_for_images
from app.pipelines.image_pipeline import prepare_product_images
from app.pipelines.publish_pipeline import (
    LocalPublishResult,
    autopublish_posts,
    create_local_publish_records,
    create_local_publish_records_for_outfit_set,
)
from app.pipelines.product_pipeline import load_cached_products_for_curator, resolve_products_from_searches
from app.scheduler import ScheduledConcept, mark_scheduled_concept_posted
from app.services.image_service import ImageService, PreparedImage


@dataclass(frozen=True)
class DailyPipelineResult:
    scheduled_concept: ScheduledConcept
    outfit: Outfit
    products: list[Product]
    prepared_images: list[PreparedImage]
    collage_path: Path
    collage_id: str | None = None
    publish_result: LocalPublishResult | None = None


@dataclass(frozen=True)
class DailyOutfitResult:
    outfit: Outfit
    products: list[Product]
    prepared_images: list[PreparedImage]
    collage_path: Path
    collage_id: str | None = None
    collage_url: str | None = None


@dataclass(frozen=True)
class DailyConceptSetResult:
    scheduled_concept: ScheduledConcept
    outfit_results: list[DailyOutfitResult]
    publish_result: LocalPublishResult | None = None


def run_daily_for_brief(
    conn: sqlite3.Connection,
    scheduled_brief: ScheduledConcept,
    *,
    outfit_output: dict[str, Any] | None = None,
    engagement_output: dict[str, Any] | None = None,
    create_publish_records: bool = True,
    settings: Settings | None = None,
) -> DailyPipelineResult:
    settings = settings or load_settings()
    t0 = time.time()

    _step("Loading cached product inventory...", 1, 5)
    cached_products = load_cached_products_for_curator(conn)
    print(f"   {len(cached_products)} cached product(s) available", flush=True)

    _step("Generating outfit spec (curator)...", 2, 5)
    outfit_output = outfit_output or generate_outfit_with_llm(
        scheduled_brief.brief,
        history=[],
        cached_products=cached_products,
    )
    outfit_output = normalize_outfit_agent_output(outfit_output)
    title = outfit_output.get("outfit", {}).get("title", "untitled")
    print(f"   Outfit: {title}", flush=True)

    _step("Searching & curating products...", 3, 5)
    products = curate_outfit_products_with_feedback(
        conn,
        outfit_output,
        tracking_id=f"concept-{scheduled_brief.concept_id}",
        settings=settings,
    )
    print(f"   {len(products)} product(s) sourced", flush=True)

    outfit = create_outfit(
        conn,
        concept_id=scheduled_brief.concept_id,
        concept_seed=scheduled_brief.seed,
        spec=outfit_output,
        product_ids=[product.id for product in products],
        metadata={
            "brief": scheduled_brief.brief,
            "source": "daily_pipeline",
        },
    )

    _step("Processing images (Runflow)...", 4, 5)
    prepared_images = prepare_product_images(
        conn,
        products,
        image_service=ImageService(settings),
    )

    _step("Rendering collage...", 5, 5)
    batch_style = generate_batch_visual_style(scheduled_brief.seed)
    categories = [p.category for p in products]
    collage_export = render_html_collage_for_images(
        prepared_images,
        output_name=f"{outfit.id}.png",
        settings=settings,
        style=batch_style,
        concept_name=scheduled_brief.seed,
        outfit_number=1,
        categories=categories,
        template_name=outfit_output.get("template"),
    )
    style_meta = {
        "background_hex": batch_style.background_hex,
        "accent_hex": batch_style.accent_hex,
        "font_style": batch_style.font_style,
        "palette_name": batch_style.palette_name,
    }
    collage = create_collage(
        conn,
        outfit_id=outfit.id,
        image_path=str(collage_export.image_path),
        collage_url=_upload_collage(outfit.id, collage_export.image_path),
        layout=_collage_manifest_with_products(collage_export.manifest, products),
        metadata={
            "renderer": "scattered",
            "source": "daily_pipeline",
            **style_meta,
        },
    )
    outfit = update_outfit_spec(
        conn,
        outfit.id,
        _spec_with_website_layout(outfit.spec, collage.layout),
    )
    publish_result = None
    if create_publish_records:
        engagement_output = engagement_output or generate_engagement_with_llm(
            scheduled_brief.brief,
            outfit.spec,
            [_product_payload(product) for product in products],
        )
        publish_result = create_local_publish_records(
            conn,
            concept_id=scheduled_brief.concept_id,
            outfit=outfit,
            products=products,
            collage_path=collage.collage_url or collage_export.image_path,
            engagement_output=engagement_output,
        )
        autopublish_posts(conn, publish_result.posts, settings=settings)
        scheduled_brief = mark_scheduled_concept_posted(conn, scheduled_brief)

    elapsed = time.time() - t0
    print(f"\n✓ Done in {elapsed:.0f}s — collage: {collage_export.image_path.name}", flush=True)

    return DailyPipelineResult(
        scheduled_concept=scheduled_brief,
        outfit=outfit,
        products=products,
        prepared_images=prepared_images,
        collage_path=collage_export.image_path,
        collage_id=collage.id,
        publish_result=publish_result,
    )


def run_daily_outfit_set_for_concept(
    conn: sqlite3.Connection,
    scheduled_concept: ScheduledConcept,
    *,
    outfit_batch_output: dict[str, Any] | None = None,
    engagement_output: dict[str, Any] | None = None,
    outfit_count: int = 5,
    create_publish_records: bool = True,
    settings: Settings | None = None,
) -> DailyConceptSetResult:
    settings = settings or load_settings()
    if outfit_count != 5:
        raise ValueError("daily concept outfit set must contain exactly 5 outfits")

    outfit_outputs = (
        normalize_outfit_agent_outputs(outfit_batch_output, expected_count=outfit_count)
        if outfit_batch_output is not None
        else generate_outfit_batch_with_llm(
            scheduled_concept.brief,
            history=[],
            outfit_count=outfit_count,
        )
    )

    # Generate visual style once for the whole batch
    batch_style = generate_batch_visual_style(scheduled_concept.seed)

    outfit_results: list[DailyOutfitResult] = []
    for index, outfit_output in enumerate(outfit_outputs, start=1):
        outfit_results.append(
            _materialize_outfit_output(
                conn,
                scheduled_concept,
                outfit_output,
                output_name_suffix=f"{index}",
                settings=settings,
                batch_style=batch_style,
                outfit_number=index,
            )
        )

    if outfit_results:
        _set_concept_cover_image_if_missing(
            conn,
            scheduled_concept.concept_id,
            str(outfit_results[0].collage_path),
        )

    publish_result = None
    if create_publish_records:
        engagement_output = engagement_output or generate_engagement_with_llm(
            scheduled_concept.brief,
            {
                "outfits": [result.outfit.spec for result in outfit_results],
                "format": "tiktok slideshow plus individual pinterest posts",
            },
            [
                _product_payload(product)
                for result in outfit_results
                for product in result.products
            ],
        )
        publish_result = create_local_publish_records_for_outfit_set(
            conn,
            concept_id=scheduled_concept.concept_id,
            outfits=[result.outfit for result in outfit_results],
            products_by_outfit=[result.products for result in outfit_results],
            collage_paths=[result.collage_url or result.collage_path for result in outfit_results],
            engagement_output=engagement_output,
        )
        autopublish_posts(conn, publish_result.posts, settings=settings)
        scheduled_concept = mark_scheduled_concept_posted(conn, scheduled_concept)

    return DailyConceptSetResult(
        scheduled_concept=scheduled_concept,
        outfit_results=outfit_results,
        publish_result=publish_result,
    )


def _materialize_outfit_output(
    conn: sqlite3.Connection,
    scheduled_concept: ScheduledConcept,
    outfit_output: dict[str, Any],
    *,
    output_name_suffix: str,
    settings: Settings,
    batch_style: BatchVisualStyle | None = None,
    outfit_number: int = 1,
) -> DailyOutfitResult:
    products = curate_outfit_products_with_feedback(
        conn,
        outfit_output,
        tracking_id=f"concept-{scheduled_concept.concept_id}",
        settings=settings,
    )
    outfit = create_outfit(
        conn,
        concept_id=scheduled_concept.concept_id,
        concept_seed=scheduled_concept.seed,
        spec=outfit_output,
        product_ids=[product.id for product in products],
        metadata={
            "brief": scheduled_concept.brief,
            "source": "daily_pipeline",
            "outfit_set_size": 5,
            "outfit_set_index": output_name_suffix,
        },
    )
    prepared_images = prepare_product_images(
        conn,
        products,
        image_service=ImageService(settings),
    )
    categories = [p.category for p in products]
    collage_export = render_html_collage_for_images(
        prepared_images,
        output_name=f"{outfit.id}-{output_name_suffix}.png",
        settings=settings,
        style=batch_style,
        concept_name=scheduled_concept.seed,
        outfit_number=outfit_number,
        categories=categories,
        template_name=outfit_output.get("template"),
    )
    style_meta = {}
    if batch_style:
        style_meta = {
            "background_hex": batch_style.background_hex,
            "accent_hex": batch_style.accent_hex,
            "font_style": batch_style.font_style,
            "palette_name": batch_style.palette_name,
        }
    collage = create_collage(
        conn,
        outfit_id=outfit.id,
        image_path=str(collage_export.image_path),
        collage_url=_upload_collage(outfit.id, collage_export.image_path),
        layout=_collage_manifest_with_products(collage_export.manifest, products),
        metadata={
            "renderer": "scattered",
            "source": "daily_pipeline",
            **style_meta,
        },
    )
    outfit = update_outfit_spec(
        conn,
        outfit.id,
        _spec_with_website_layout(outfit.spec, collage.layout),
    )
    return DailyOutfitResult(
        outfit=outfit,
        products=products,
        prepared_images=prepared_images,
        collage_path=collage_export.image_path,
        collage_id=collage.id,
        collage_url=collage.collage_url,
    )


def _upload_collage(outfit_id: str, image_path: Path) -> str | None:
    """Upload a rendered collage to Supabase storage; return its public URL.

    Best-effort: returns None if storage isn't configured or the upload fails,
    so collage hosting never breaks the pipeline.
    """
    from app.services.asset_storage import asset_storage_from_env

    try:
        storage = asset_storage_from_env()
        if storage is None:
            return None
        return storage.upload_collage(outfit_id, image_path)
    except Exception:  # noqa: BLE001
        return None


def _collage_manifest_with_products(manifest: dict[str, Any], products: list[Product]) -> dict[str, Any]:
    manifest = dict(manifest)
    pieces = []
    for piece, product in zip(manifest["pieces"], products, strict=True):
        pieces.append({**piece, "product_id": product.id})
    manifest["pieces"] = pieces
    return manifest


def _spec_with_website_layout(spec: dict[str, Any], collage_layout: dict[str, Any]) -> dict[str, Any]:
    updated = dict(spec)
    updated["layout"] = _website_product_layout(collage_layout)
    return updated


def _website_product_layout(collage_layout: dict[str, Any]) -> list[dict[str, Any]]:
    canvas = collage_layout.get("canvas", {})
    canvas_width = _positive_number(canvas.get("width"), "canvas.width")
    canvas_height = _positive_number(canvas.get("height"), "canvas.height")

    layout: list[dict[str, Any]] = []
    for index, piece in enumerate(collage_layout.get("pieces", [])):
        product_id = piece.get("product_id")
        if not isinstance(product_id, str) or not product_id:
            continue
        layout.append(
            {
                "product_id": product_id,
                "x": round(float(piece["x"]) / canvas_width * 100, 4),
                "y": round(float(piece["y"]) / canvas_height * 100, 4),
                "width": round(float(piece["width"]) / canvas_width * 100, 4),
                "rotation": float(piece.get("rotation", 0)),
                "z_index": int(piece.get("z_index", index + 1)),
            }
        )
    return layout


def _positive_number(value: Any, field: str) -> float:
    if not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"collage layout field '{field}' must be a positive number")
    return float(value)


def _set_concept_cover_image_if_missing(
    conn: sqlite3.Connection,
    concept_id: str,
    cover_image_url: str,
) -> None:
    concept = get_concept(conn, concept_id)
    metadata = dict(concept.metadata)
    if metadata.get("cover_image_url"):
        return
    metadata["cover_image_url"] = cover_image_url
    update_concept_metadata(conn, concept_id, metadata)


def _product_payload(product: Product) -> dict[str, Any]:
    return {
        "id": product.id,
        "retailer": product.retailer,
        "name": product.name,
        "category": product.category,
        "price_cents": product.price_cents,
        "currency": product.currency,
        "affiliate_url": product.affiliate_url,
        "metadata": product.metadata,
    }
