from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from app.config import Settings, load_settings
from app.services.retailer_service import ProductFixture, search_product_fixtures


SERPAPI_SEARCH_URL = "https://serpapi.com/search.json"
BLOCKED_RETAILER_TERMS = {
    "aliexpress",
    "dhgate",
    "lightinthebox",
    "romwe",
    "temu",
    "wish",
    "zaful",
}
CONDITIONAL_RETAILER_TERMS = {"shein"}
LOW_STAKES_CATEGORY_TERMS = {
    "accessory",
    "accessories",
    "bag",
    "cap",
    "costume",
    "gimmick",
    "hair",
    "hat",
    "jewelry",
    "sunglasses",
}


@dataclass(frozen=True)
class ProductSearchResult:
    retailer: str
    name: str
    url: str
    category: str | None = None
    image_url: str | None = None
    price_cents: int | None = None
    currency: str = "USD"
    source: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)


class ProductSearchProvider(Protocol):
    def search(
        self,
        query: str,
        *,
        category: str | None = None,
        limit: int = 5,
    ) -> list[ProductSearchResult]:
        ...


class FixtureProductSearchProvider:
    def __init__(self, fixtures: list[ProductFixture] | None = None) -> None:
        self.fixtures = fixtures

    def search(
        self,
        query: str,
        *,
        category: str | None = None,
        limit: int = 5,
    ) -> list[ProductSearchResult]:
        matches = search_product_fixtures(
            query,
            category=category,
            limit=limit,
            fixtures=self.fixtures,
        )
        return [
            ProductSearchResult(
                retailer=match.fixture.retailer,
                name=match.fixture.name,
                url=match.fixture.url,
                category=match.fixture.category,
                image_url=match.fixture.image_url,
                price_cents=match.fixture.price_cents,
                currency=match.fixture.currency,
                source="fixture",
                metadata={
                    **match.fixture.metadata,
                    "tags": match.fixture.tags,
                    "colors": match.fixture.colors,
                    "match_score": match.score,
                    "matched_terms": match.matched_terms,
                },
            )
            for match in matches
        ]


class SerpApiGoogleShoppingProvider:
    def __init__(
        self,
        *,
        api_key: str,
        location: str = "United States",
        gl: str = "us",
        hl: str = "en",
        timeout_seconds: int = 30,
    ) -> None:
        if not api_key:
            raise ValueError("SERPAPI_API_KEY is required when PRODUCT_SEARCH_PROVIDER=google_shopping")
        self.api_key = api_key
        self.location = location
        self.gl = gl
        self.hl = hl
        self.timeout_seconds = timeout_seconds

    def search(
        self,
        query: str,
        *,
        category: str | None = None,
        limit: int = 5,
    ) -> list[ProductSearchResult]:
        if limit < 1:
            raise ValueError("limit must be at least 1")

        params = {
            "engine": "google_shopping",
            "q": query,
            "api_key": self.api_key,
            "gl": self.gl,
            "hl": self.hl,
        }
        if self.location:
            params["location"] = self.location

        request = Request(
            f"{SERPAPI_SEARCH_URL}?{urlencode(params)}",
            headers={"User-Agent": "affiliate-outfits/0.1"},
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))

        if isinstance(payload.get("error"), str):
            raise RuntimeError(f"SerpApi Google Shopping error: {payload['error']}")

        results = [
            _result_from_serpapi_item(item, category=category)
            for item in payload.get("shopping_results", [])
            if isinstance(item, dict)
        ]
        return rank_product_results(results, category=category)[:limit]


def product_search_provider_from_settings(settings: Settings | None = None) -> ProductSearchProvider:
    settings = settings or load_settings()
    if settings.product_search_provider in {"google_shopping", "serpapi"}:
        return SerpApiGoogleShoppingProvider(
            api_key=settings.serpapi_api_key or "",
            location=settings.google_shopping_location,
            gl=settings.google_shopping_gl,
            hl=settings.google_shopping_hl,
        )
    if settings.product_search_provider == "fixtures":
        return FixtureProductSearchProvider()
    raise ValueError(f"unsupported PRODUCT_SEARCH_PROVIDER: {settings.product_search_provider}")


def rank_product_results(
    results: list[ProductSearchResult],
    *,
    category: str | None = None,
) -> list[ProductSearchResult]:
    allowed = [
        result
        for result in results
        if is_allowed_retailer(result.retailer, result.url, category=category or result.category)
    ]
    return sorted(
        allowed,
        key=lambda result: (
            result.price_cents is None,
            result.price_cents or 10**12,
            _normal(result.retailer),
            _normal(result.name),
        ),
    )


def is_allowed_retailer(retailer: str, url: str, *, category: str | None = None) -> bool:
    haystack = f"{retailer} {urlparse(url).netloc}".lower()
    if any(term in haystack for term in BLOCKED_RETAILER_TERMS):
        return False
    if any(term in haystack for term in CONDITIONAL_RETAILER_TERMS):
        return _is_low_stakes_category(category)
    return True


def _result_from_serpapi_item(item: dict[str, Any], *, category: str | None) -> ProductSearchResult:
    name = _clean_text(item.get("title")) or "Untitled product"
    retailer = _clean_text(item.get("source")) or _retailer_from_url(_clean_text(item.get("link")) or "")
    url = _clean_text(item.get("link")) or _clean_text(item.get("product_link")) or ""
    if not url:
        raise ValueError("Google Shopping result did not include a product URL")

    return ProductSearchResult(
        retailer=retailer or "Unknown retailer",
        name=name,
        url=url,
        category=category,
        image_url=_clean_text(item.get("thumbnail")),
        price_cents=_price_to_cents(item.get("extracted_price")) or _parse_price(item.get("price")),
        currency=_currency_from_price(item.get("price")) or "USD",
        source="google_shopping",
        metadata={
            "google_shopping_position": item.get("position"),
            "google_product_id": item.get("product_id"),
            "rating": item.get("rating"),
            "reviews": item.get("reviews"),
        },
    )


def _clean_text(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _retailer_from_url(url: str) -> str:
    host = urlparse(url).netloc.removeprefix("www.")
    return host.split(".")[0].title() if host else "Unknown retailer"


def _price_to_cents(value: Any) -> int | None:
    if isinstance(value, (int, float)):
        return max(0, round(float(value) * 100))
    return None


def _parse_price(value: Any) -> int | None:
    if not isinstance(value, str):
        return None
    match = re.search(r"([0-9]+(?:\.[0-9]{1,2})?)", value.replace(",", ""))
    if not match:
        return None
    return round(float(match.group(1)) * 100)


def _currency_from_price(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    if "$" in value:
        return "USD"
    return None


def _is_low_stakes_category(category: str | None) -> bool:
    if not category:
        return False
    terms = set(re.split(r"[^a-z0-9]+", category.lower()))
    return bool(terms.intersection(LOW_STAKES_CATEGORY_TERMS))


def _normal(value: str) -> str:
    return value.lower().strip()
