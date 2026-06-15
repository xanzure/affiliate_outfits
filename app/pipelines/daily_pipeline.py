from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.agents.outfit.parser import normalize_outfit_agent_output, normalize_outfit_agent_outputs
from app.agents.engagement.agent import generate_engagement_with_llm
from app.agents.outfit.agent import generate_outfit_batch_with_llm, generate_outfit_with_llm
from app.config import Settings, load_settings
from app.db.collages import create_collage
from app.db.concepts import get_concept, update_concept_metadata
from app.db.models import Outfit, Product
from app.db.outfits import create_outfit, update_outfit_spec
from app.pipelines.collage_pipeline import render_collage_manifest_for_images
from app.pipelines.image_pipeline import prepare_product_images
from app.pipelines.publish_pipeline import (
    LocalPublishResult,
    autopublish_posts,
    create_local_publish_records,
    create_local_publish_records_for_outfit_set,
)
from app.pipelines.product_pipeline import (
    resolve_products_from_searches,
    search_specs_from_agent_output,
)
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
    outfit_output = outfit_output or generate_outfit_with_llm(
        scheduled_brief.brief,
        history=[],
    )
    outfit_output = normalize_outfit_agent_output(outfit_output)

    searches = search_specs_from_agent_output(outfit_output)
    products = resolve_products_from_searches(
        conn,
        searches,
        tracking_id=f"concept-{scheduled_brief.concept_id}",
        settings=settings,
    )
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
    prepared_images = prepare_product_images(
        conn,
        products,
        image_service=ImageService(settings),
    )
    collage_export = render_collage_manifest_for_images(
        prepared_images,
        output_name=f"{outfit.id}.png",
        settings=settings,
    )
    collage = create_collage(
        conn,
        outfit_id=outfit.id,
        image_path=str(collage_export.image_path),
        layout=_collage_manifest_with_products(collage_export.manifest, products),
        metadata={
            "renderer": "deterministic_grid",
            "source": "daily_pipeline",
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
            collage_path=collage_export.image_path,
            engagement_output=engagement_output,
        )
        autopublish_posts(conn, publish_result.posts, settings=settings)
        scheduled_brief = mark_scheduled_concept_posted(conn, scheduled_brief)

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

    outfit_results: list[DailyOutfitResult] = []
    for index, outfit_output in enumerate(outfit_outputs, start=1):
        outfit_results.append(
            _materialize_outfit_output(
                conn,
                scheduled_concept,
                outfit_output,
                output_name_suffix=f"{index}",
                settings=settings,
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
            collage_paths=[result.collage_path for result in outfit_results],
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
) -> DailyOutfitResult:
    searches = search_specs_from_agent_output(outfit_output)
    products = resolve_products_from_searches(
        conn,
        searches,
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
    collage_export = render_collage_manifest_for_images(
        prepared_images,
        output_name=f"{outfit.id}-{output_name_suffix}.png",
        settings=settings,
    )
    collage = create_collage(
        conn,
        outfit_id=outfit.id,
        image_path=str(collage_export.image_path),
        layout=_collage_manifest_with_products(collage_export.manifest, products),
        metadata={
            "renderer": "deterministic_grid",
            "source": "daily_pipeline",
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
    )


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
