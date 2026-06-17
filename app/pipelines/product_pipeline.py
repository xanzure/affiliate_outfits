from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from typing import Any

from app.db.models import Product
from app.db.products import list_products, upsert_product
from app.config import Settings, load_settings
from app.services.affiliate_service import (
    AffiliateResolver,
    affiliate_resolver_from_name,
)
from app.services.product_search_service import (
    ProductSearchProvider,
    ProductSearchResult,
    product_search_provider_from_settings,
    rank_product_results,
)


@dataclass(frozen=True)
class ProductSearchSpec:
    query: str
    category: str | None = None
    limit: int = 5


def resolve_products_from_searches(
    conn: sqlite3.Connection,
    searches: list[ProductSearchSpec],
    *,
    tracking_id: str = "local-dev",
    search_provider: ProductSearchProvider | None = None,
    affiliate_resolver: AffiliateResolver | None = None,
    settings: Settings | None = None,
) -> list[Product]:
    settings = settings or load_settings()
    search_provider = search_provider or product_search_provider_from_settings(settings)
    affiliate_resolver = affiliate_resolver or affiliate_resolver_from_name(settings.affiliate_provider)
    products: list[Product] = []
    seen_urls: set[str] = set()

    # Run all searches in parallel
    provider_name = settings.product_search_provider
    print(f"   Searching {len(searches)} queries in parallel via {provider_name}...", flush=True)
    results: list[list[ProductSearchResult]] = [[] for _ in searches]

    def _do_search(i: int, search: ProductSearchSpec) -> None:
        try:
            candidates = search_provider.search(
                search.query,
                category=search.category,
                limit=max(search.limit, 5),
            )
            results[i] = rank_product_results(candidates, category=search.category)
        except Exception:
            results[i] = []

    threads = [threading.Thread(target=_do_search, args=(i, s)) for i, s in enumerate(searches)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    for i, ranked in enumerate(results):
        stored = _store_product_candidates(
            conn,
            ranked,
            tracking_id=tracking_id,
            affiliate_resolver=affiliate_resolver,
        )
        selected = next((p for p in stored if p.url not in seen_urls), None)
        if selected is None:
            continue
        seen_urls.add(selected.url)
        products.append(selected)

    return products


def _store_product_candidates(
    conn: sqlite3.Connection,
    candidates: list[ProductSearchResult],
    *,
    tracking_id: str,
    affiliate_resolver: AffiliateResolver,
) -> list[Product]:
    products: list[Product] = []
    for index, candidate in enumerate(candidates, start=1):
        affiliate = affiliate_resolver.resolve(
            candidate.url,
            retailer=candidate.retailer,
            tracking_id=tracking_id,
        )
        products.append(
            upsert_product(
                conn,
                retailer=candidate.retailer,
                name=candidate.name,
                category=candidate.category,
                url=candidate.url,
                affiliate_url=affiliate.affiliate_url or None,
                image_url=candidate.image_url,
                price_cents=candidate.price_cents,
                currency=candidate.currency,
                metadata={
                    **candidate.metadata,
                    "product_source": candidate.source,
                    "candidate_rank": index,
                    "affiliate_network": affiliate.network,
                },
            )
        )
    return products


def resolve_cached_product(conn: sqlite3.Connection, url: str) -> Product | None:
    """Return an existing DB product by URL if it exists, else None."""
    try:
        rows = conn.execute(
            "SELECT * FROM products WHERE url = ? LIMIT 1", (url,)
        ).fetchall()
        if not rows:
            return None
        from app.db.products import _to_product
        return _to_product(rows[0])
    except Exception:
        return None


def load_cached_products_for_curator(conn: sqlite3.Connection) -> list[dict]:
    """Return all products that have processed images, formatted for the curator prompt."""
    try:
        products = list_products(conn)
        return [
            {
                "name": p.name,
                "retailer": p.retailer,
                "category": p.category,
                "price_cents": p.price_cents,
                "url": p.url,
            }
            for p in products
            if p.image_url and ("supabase.co/storage" in p.image_url or p.local_image_path)
        ]
    except Exception:
        return []


def search_specs_from_agent_output(agent_output: dict[str, Any]) -> list[ProductSearchSpec]:
    raw_queries = agent_output.get("search_queries", [])
    if not isinstance(raw_queries, list):
        raise ValueError("agent output field 'search_queries' must be a list")

    specs: list[ProductSearchSpec] = []
    for item in raw_queries:
        if isinstance(item, str):
            specs.append(ProductSearchSpec(query=item))
            continue

        if not isinstance(item, dict):
            raise ValueError("search query entries must be strings or objects")

        query = item.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("search query object must include a non-empty 'query'")

        category = item.get("category")
        if category is not None and not isinstance(category, str):
            raise ValueError("search query field 'category' must be a string when present")

        limit = item.get("limit", 3)
        if not isinstance(limit, int) or limit < 1:
            raise ValueError("search query field 'limit' must be a positive integer")

        specs.append(ProductSearchSpec(query=query, category=category, limit=limit))

    return specs
