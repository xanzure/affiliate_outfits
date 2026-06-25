from __future__ import annotations

import logging
import sqlite3
from typing import Any

from app.agents.outfit.curator import (
    CuratorReview,
    generate_outfit_specs,
    make_curator_service,
    outfit_spec_to_pipeline_format,
    outfit_spec_to_search_queries,
    review_found_products,
)
from app.agents.outfit.parser import normalize_outfit_agent_output, normalize_outfit_agent_outputs
from app.collage.export import _resolve_zone
from app.db.models import Product
from app.services.llm_service import ClaudeJSONService
from app.services.product_cache import find_cached_match

log = logging.getLogger(__name__)

_MAX_REVIEW_ROUNDS = 1


def generate_outfit_with_llm(
    brief: dict[str, Any],
    history: list[dict[str, Any]] | None = None,
    *,
    llm_service: ClaudeJSONService | None = None,
    cached_products: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    service = llm_service or make_curator_service()
    specs = generate_outfit_specs(brief, 1, history or [], service=service, cached_products=cached_products)
    return normalize_outfit_agent_output(outfit_spec_to_pipeline_format(specs[0]))


def generate_outfit_batch_with_llm(
    brief: dict[str, Any],
    history: list[dict[str, Any]] | None = None,
    *,
    outfit_count: int,
    llm_service: ClaudeJSONService | None = None,
    cached_products: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    service = llm_service or make_curator_service()
    specs = generate_outfit_specs(brief, outfit_count, history or [], service=service, cached_products=cached_products)
    return normalize_outfit_agent_outputs(
        {"outfits": [outfit_spec_to_pipeline_format(s) for s in specs]},
        expected_count=outfit_count,
    )


def curate_outfit_products_with_feedback(
    conn: sqlite3.Connection,
    outfit_spec: dict[str, Any],
    *,
    tracking_id: str = "local-dev",
    settings: Any = None,
    service: ClaudeJSONService | None = None,
) -> list[Product]:
    """
    Full curator feedback loop: search → review → refine → repeat.
    Returns the best products the curator approved (or best found after max rounds).
    """
    from app.pipelines.product_pipeline import (
        ProductSearchSpec,
        resolve_products_from_searches,
        resolve_cached_product,
    )
    from app.config import load_settings

    settings = settings or load_settings()
    service = service or make_curator_service()

    # Start with the queries from the outfit spec
    current_queries = outfit_spec_to_search_queries(outfit_spec)
    best_products: list[Product] = []

    for round_num in range(1, _MAX_REVIEW_ROUNDS + 1):
        log.info("Curator search round %d/%d", round_num, _MAX_REVIEW_ROUNDS)

        products: list[Product] = []
        search_specs = []

        for q in current_queries:
            # 1) explicit LLM reuse (exact URL it picked from cached inventory)
            cached_url = q.get("use_cached_url")
            if cached_url:
                cached = resolve_cached_product(conn, cached_url)
                if cached:
                    log.info("  Using cached product (LLM): %s", cached.name[:60])
                    products.append(cached)
                    continue
            # 2) deterministic near-match gate — reuse a close cached product
            #    (same zone + colour family + garment type) before paying to search
            near = find_cached_match(
                conn,
                zone=_resolve_zone(q.get("category")),
                color=q.get("color"),
                descriptor=f"{q.get('category') or ''} {q.get('query') or ''}",
            )
            if near is not None:
                log.info("  Reusing near-match cached product: %s", near.name[:60])
                products.append(near)
                continue
            search_specs.append(
                ProductSearchSpec(
                    query=q["query"],
                    category=q.get("category"),
                    limit=q.get("limit", 5),
                    color=q.get("color"),
                    material=q.get("material"),
                )
            )

        searched = resolve_products_from_searches(
            conn,
            search_specs,
            tracking_id=tracking_id,
            settings=settings,
        )
        products.extend(searched)

        if not products:
            log.warning("No products found in round %d", round_num)
            break

        best_products = products

        # Curator reviews what was found
        product_dicts = [
            {
                "name": p.name,
                "retailer": p.retailer,
                "category": p.category,
                "price_cents": p.price_cents,
                "url": p.url,
            }
            for p in products
        ]
        review = review_found_products(outfit_spec, product_dicts, service=service)

        if review.overall_approved:
            log.info("Curator approved outfit after round %d", round_num)
            break

        if round_num == _MAX_REVIEW_ROUNDS:
            log.info("Max rounds reached — using best products found")
            break

        # Build refined queries for rejected items only
        refined: list[dict[str, Any]] = []
        for i, (query, item_review) in enumerate(
            zip(current_queries, review.items or [])
        ):
            if not item_review.approved and item_review.refined_query:
                refined.append({
                    **query,
                    "query": item_review.refined_query,
                })
            else:
                refined.append(query)
        current_queries = refined

    return best_products
