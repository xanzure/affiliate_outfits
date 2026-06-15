from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT
from app.db.models import Product
from app.db.products import upsert_product
from app.services.affiliate_service import AffiliateResolver, NoAffiliateResolver


DEFAULT_PRODUCTS_PATH = PROJECT_ROOT / "data/retailer_cache/products.json"


@dataclass(frozen=True)
class ProductFixture:
    retailer: str
    name: str
    url: str
    category: str
    tags: list[str] = field(default_factory=list)
    colors: list[str] = field(default_factory=list)
    price_cents: int | None = None
    currency: str = "USD"
    image_url: str | None = None
    local_image_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProductMatch:
    fixture: ProductFixture
    score: int
    matched_terms: list[str]


def load_product_fixtures(path: Path = DEFAULT_PRODUCTS_PATH) -> list[ProductFixture]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError("product fixture file must contain a JSON array")
    return [_fixture_from_dict(item) for item in value]


def search_product_fixtures(
    query: str,
    *,
    category: str | None = None,
    limit: int = 5,
    fixtures: list[ProductFixture] | None = None,
) -> list[ProductMatch]:
    if limit < 1:
        raise ValueError("limit must be at least 1")

    fixtures = fixtures or load_product_fixtures()
    query_terms = _tokenize(query)
    matches: list[ProductMatch] = []

    for fixture in fixtures:
        if category and fixture.category != category:
            continue

        haystack_terms = _fixture_terms(fixture)
        matched_terms = sorted(query_terms.intersection(haystack_terms))
        score = len(matched_terms)
        if category and fixture.category == category:
            score += 2

        if score > 0:
            matches.append(ProductMatch(fixture=fixture, score=score, matched_terms=matched_terms))

    return sorted(
        matches,
        key=lambda item: (-item.score, item.fixture.price_cents or 10**12, item.fixture.name),
    )[:limit]


def store_product_matches(
    conn: sqlite3.Connection,
    matches: list[ProductMatch],
    *,
    affiliate_resolver: AffiliateResolver | None = None,
    tracking_id: str = "local-dev",
) -> list[Product]:
    affiliate_resolver = affiliate_resolver or NoAffiliateResolver()
    products: list[Product] = []
    for match in matches:
        fixture = match.fixture
        affiliate = affiliate_resolver.resolve(
            fixture.url,
            retailer=fixture.retailer,
            tracking_id=tracking_id,
        )
        products.append(
            upsert_product(
                conn,
                retailer=fixture.retailer,
                name=fixture.name,
                category=fixture.category,
                url=fixture.url,
                affiliate_url=affiliate.affiliate_url or None,
                image_url=fixture.image_url,
                local_image_path=fixture.local_image_path,
                price_cents=fixture.price_cents,
                currency=fixture.currency,
                metadata={
                    **fixture.metadata,
                    "tags": fixture.tags,
                    "colors": fixture.colors,
                    "match_score": match.score,
                    "matched_terms": match.matched_terms,
                    "affiliate_network": affiliate.network,
                },
            )
        )
    return products


def _fixture_from_dict(value: Any) -> ProductFixture:
    if not isinstance(value, dict):
        raise ValueError("product fixture entries must be JSON objects")

    required = ("retailer", "name", "url", "category")
    for field_name in required:
        if not isinstance(value.get(field_name), str) or not value[field_name].strip():
            raise ValueError(f"product fixture field '{field_name}' must be a non-empty string")

    return ProductFixture(
        retailer=value["retailer"].strip(),
        name=value["name"].strip(),
        url=value["url"].strip(),
        category=value["category"].strip(),
        tags=_string_list(value.get("tags", []), "tags"),
        colors=_string_list(value.get("colors", []), "colors"),
        price_cents=value.get("price_cents"),
        currency=value.get("currency", "USD"),
        image_url=value.get("image_url"),
        local_image_path=value.get("local_image_path"),
        metadata=value.get("metadata", {}),
    )


def _string_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"product fixture field '{field_name}' must be a list")
    if not all(isinstance(item, str) for item in value):
        raise ValueError(f"product fixture field '{field_name}' must contain only strings")
    return [item.strip().lower() for item in value if item.strip()]


def _tokenize(value: str) -> set[str]:
    return {token for token in re.split(r"[^a-z0-9]+", value.lower()) if token}


def _fixture_terms(fixture: ProductFixture) -> set[str]:
    values = [
        fixture.retailer,
        fixture.name,
        fixture.category,
        *fixture.tags,
        *fixture.colors,
    ]
    terms: set[str] = set()
    for value in values:
        terms.update(_tokenize(value))
    return terms
