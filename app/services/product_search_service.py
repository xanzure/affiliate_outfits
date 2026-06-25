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
    # Resale / secondhand marketplaces — no affiliate links, unpredictable stock
    "poshmark",
    "thredup",
    "depop",
    "mercari",
    "ebay",
    "etsy",
    "vinted",
    "vestiaire",
    "tradesy",
    "therealreal",
}
CONDITIONAL_RETAILER_TERMS: set[str] = set()  # shein and amazon now allowed

# Raw materials / craft / furniture / home goods — search matches material words
# ("leather", "silk", "suede") to these, and we'd pay to cut out images of cloth
# and couches. Reject by product-name signal or retailer.
NONAPPAREL_NAME_TERMS = {
    "fabric", "cowhide", "microsuede", "upholstery", "yardage", "by the yard",
    "leather by", "make market", "tooling", "crust leather", "swatch", "bolt of",
    "sofa", "couch", "sectional", "recliner", "ottoman", "armchair", "chair",
    "stool", "pillow", "pillowcase", "duvet", "comforter", "curtain", "area rug",
    "mattress", "bedding", "tablecloth", "wallpaper",
    "yarn", "skein", "roving", "knitting kit",  # NOT "crochet"/"embroidered" — those are real garments
}
NONAPPAREL_RETAILER_TERMS = {
    "michaels", "hobbylobby", "hobby lobby", "joann", "fabricwholesale",
    "leatherunlt", "handweavers", "hancocks", "nochka", "elwshop", "lumens",
    "overstock", "ostkcdn", "ashleyfurniture", "wayfair", "desertcart",
}


def is_apparel_result(name: str | None, retailer: str | None, url: str) -> bool:
    text = (name or "").lower()
    if any(term in text for term in NONAPPAREL_NAME_TERMS):
        return False
    haystack = f"{retailer or ''} {urlparse(url).netloc}".lower()
    if any(term in haystack for term in NONAPPAREL_RETAILER_TERMS):
        return False
    return True
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


class TavilyProductSearchProvider:
    """
    Uses Tavily's web search API to find real product pages.
    Returns actual retailer URLs with names and prices extracted from results.
    """

    TAVILY_URL = "https://api.tavily.com/search"

    # Retailers that publish clean product pages worth scraping
    INCLUDE_DOMAINS = [
        "asos.com", "revolve.com", "nordstrom.com", "freepeople.com",
        "urbanoutfitters.com", "anthropologie.com", "cos.com", "stories.com",
        "zara.com", "mango.com", "hm.com", "uniqlo.com", "gap.com",
        "lululemon.com", "nike.com", "adidas.com", "newbalance.com",
        "converse.com", "vans.com", "stevemadden.com", "samedelman.com",
        "levi.com", "madewell.com", "agolde.com", "frame-store.com",
        "everlane.com", "reformation.com", "aritzia.com", "theory.com",
        "bananarepublic.gap.com", "jcrew.com", "ralphlauren.com",
        "abercrombie.com", "ae.com", "express.com",
        "shopbop.com", "saksfifthavenue.com", "bloomingdales.com",
        "net-a-porter.com", "ssense.com", "farfetch.com",
        "amazon.com", "zappos.com", "dsw.com", "footlocker.com",
    ]

    def __init__(self, *, api_key: str, timeout_seconds: int = 30) -> None:
        if not api_key:
            raise ValueError("TAVILY_API_KEY is required when PRODUCT_SEARCH_PROVIDER=tavily")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def search(
        self,
        query: str,
        *,
        category: str | None = None,
        limit: int = 5,
    ) -> list[ProductSearchResult]:
        search_query = f"{query} site:product"

        payload = json.dumps({
            "api_key": self.api_key,
            "query": search_query,
            "search_depth": "advanced",
            "max_results": min(limit * 3, 15),
            "include_answer": False,
            "include_images": True,
            "include_domains": self.INCLUDE_DOMAINS,
        }).encode("utf-8")

        request = Request(
            self.TAVILY_URL,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "affiliate-outfits/0.1"},
            method="POST",
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))

        # Top-level images are the cleanest — Tavily curates these per query
        top_images: list[str] = [
            u for u in data.get("images", [])
            if _looks_like_product_image(u)
        ]

        results = []
        for i, item in enumerate(data.get("results", [])):
            result = self._item_to_result(item, category=category, top_images=top_images, rank=i)
            if result:
                results.append(result)

        return rank_product_results(results, category=category)[:limit]

    def _item_to_result(
        self,
        item: dict[str, Any],
        *,
        category: str | None,
        top_images: list[str] | None = None,
        rank: int = 0,
    ) -> ProductSearchResult | None:
        url = item.get("url", "")
        title = _clean_text(item.get("title")) or ""
        content = item.get("content", "")

        if not url or not title:
            return None

        skip_domains = {
            "pinterest", "reddit", "youtube", "instagram", "tiktok", "wikipedia",
            "businessinsider", "buzzfeed", "refinery29", "whowhatwear", "byrdie",
            "lyst", "poshmark", "depop", "ebay", "etsy", "mercari",
        }
        netloc = urlparse(url).netloc.lower()
        if any(d in netloc for d in skip_domains):
            return None

        path = urlparse(url).path.lower()
        skip_path_patterns = ["/cat", "/category", "/shop", "/market", "/search", "/guides/", "/c/"]
        query_string = urlparse(url).query.lower()
        if any(p in path for p in skip_path_patterns) and not _looks_like_product_url(url):
            return None
        if "cid=" in query_string or "cat=" in query_string:
            return None

        retailer = _retailer_from_url(url)
        price_cents = _extract_price_from_text(content) or _extract_price_from_text(title)

        # Prefer top-level images (Tavily-curated, cleanest) indexed by result rank,
        # then fall back to per-result images list
        image_url: str | None = None
        if top_images and rank < len(top_images):
            image_url = top_images[rank]
        if not image_url:
            per_result = [u for u in (item.get("images") or []) if _looks_like_product_image(u)]
            image_url = per_result[0] if per_result else None

        return ProductSearchResult(
            retailer=retailer,
            name=title,
            url=url,
            category=category,
            image_url=image_url,
            price_cents=price_cents,
            currency="USD",
            source="tavily",
            metadata={"snippet": content[:200]},
        )


def _looks_like_product_image(url: str) -> bool:
    """Filter out logos, icons, and banners — keep CDN product images."""
    skip = {"logo", "icon", "banner", "cookie", "avatar", "sprite", "placeholder", "pixel", "tracking"}
    lower = url.lower()
    if any(s in lower for s in skip):
        return False
    # Must look like an image file or CDN path
    return any(ext in lower for ext in (".jpg", ".jpeg", ".png", ".webp", "/images/", "/media/", "/cdn/", "asos-media", "media.mango", "nordstrom", "revolve"))


def _looks_like_product_url(url: str) -> bool:
    """Heuristic: does this URL look like a single product page?"""
    path = urlparse(url).path.lower()
    # Product URLs typically have /p/, /dp/, /product/, or a long slug with ID
    product_signals = ["/p/", "/dp/", "/product/", "/products/", "/item/", "/pd/", "/prd/"]
    if any(s in path for s in product_signals):
        return True
    # Long paths with numbers often indicate product pages
    import re
    if re.search(r'/[a-z0-9-]{20,}', path):
        return True
    return False


def _scrape_image_url(url: str) -> str | None:
    """Fetch a product page and extract its main product image URL."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        # Try Playwright first — handles JS-heavy retail sites
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                ctx = browser.new_context(user_agent=headers["User-Agent"], locale="en-US")
                page = ctx.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(1000)
                html = page.content()
                browser.close()
        except ImportError:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="replace")

        return _extract_image_from_html(html)
    except Exception:
        return None


def _extract_image_from_html(html: str) -> str | None:
    import re as _re
    import json as _json

    # JSON-LD product image
    for block in _re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, _re.S):
        try:
            data = _json.loads(block)
            items = data if isinstance(data, list) else [data]
            for item in items:
                if not isinstance(item, dict) or item.get("@type") not in ("Product", "product"):
                    continue
                img = item.get("image")
                if isinstance(img, list): img = img[0]
                if isinstance(img, dict): img = img.get("url")
                if img and isinstance(img, str):
                    return img
        except Exception:
            pass

    # OG image
    m = _re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"', html, _re.I)
    if m:
        return m.group(1).strip()

    # twitter:image
    m = _re.search(r'<meta[^>]*name="twitter:image"[^>]*content="([^"]+)"', html, _re.I)
    if m:
        return m.group(1).strip()

    return None


def _extract_price_from_text(text: str) -> int | None:
    """Pull the first dollar price out of a text snippet."""
    match = re.search(r"\$\s*([0-9]+(?:\.[0-9]{1,2})?)", text)
    if match:
        return round(float(match.group(1)) * 100)
    return None


class AWINProductSearchProvider:
    """Queries the local AWIN product catalog (populated by sync_awin_feeds.py)."""

    def __init__(self, catalog_path: Path) -> None:
        from app.db.awin_catalog import connect_catalog
        self._conn = connect_catalog(catalog_path)

    def search(
        self,
        query: str,
        *,
        category: str | None = None,
        limit: int = 5,
    ) -> list[ProductSearchResult]:
        from app.db.awin_catalog import search_catalog
        hits = search_catalog(self._conn, query, category=category, limit=limit * 2)
        results = [
            ProductSearchResult(
                retailer=h.merchant_name,
                name=h.product_name,
                url=h.product_url or h.affiliate_url,
                category=h.category or category,
                image_url=h.image_url,
                price_cents=h.price_cents,
                currency=h.currency,
                source="awin_catalog",
                metadata={
                    "affiliate_url": h.affiliate_url,
                    "awin_product_id": h.aw_product_id,
                    "colour": h.colour,
                    "brand": h.brand_name,
                },
            )
            for h in hits
        ]
        return rank_product_results(results, category=category)[:limit]


class ApifyEcommerceProvider:
    """Apify 'E-commerce Scraping Tool' in search-engine Products mode.

    Discovers products via search engine, then deep-scrapes each real merchant
    product page — returning clean retailer-CDN images and true product URLs
    (unlike Google Shopping, which only gives thumbnails + redirect links).
    """

    ACTOR_ID = "2APbAvDfNDOWXbkWf"
    RUN_URL = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items?token={token}"

    def __init__(self, *, api_token: str, country_code: str = "us", timeout_seconds: int = 300) -> None:
        if not api_token:
            raise ValueError("APIFY_TOKEN is required when PRODUCT_SEARCH_PROVIDER=apify")
        self.api_token = api_token
        self.country_code = country_code
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

        # Apify charges per product SCRAPED, before our retailer filter runs, and
        # there's no source-level retailer blacklist (marketplaces enum is mass
        # retailers only; Google -site: operators don't pass through). So keep the
        # over-fetch small — retailer-named queries surface the real store near the
        # top, so a modest candidate count yields clean results without paying to
        # scrape a pile of eBay/Poshmark listings we'd only throw away.
        # ponytail: tune this number if yield is too thin — it's the cost dial.
        max_candidates = min(max(limit + 2, 6), 8)
        payload = json.dumps({
            "searchEngineKeyword": query,
            "countryCode": self.country_code,
            "scrapeModeSearchEngine": "Products",
            "maxSearchEngineProducts": max_candidates,
        }).encode("utf-8")
        url = self.RUN_URL.format(actor=self.ACTOR_ID, token=self.api_token)
        request = Request(
            url, data=payload, method="POST",
            headers={"Content-Type": "application/json", "User-Agent": "affiliate-outfits/0.1"},
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            items = json.loads(response.read().decode("utf-8"))

        results = [
            r for r in (_result_from_apify_item(item, category=category) for item in items if isinstance(item, dict))
            if r is not None
        ]
        return rank_product_results(results, category=category)[:limit]


def _result_from_apify_item(item: dict[str, Any], *, category: str | None) -> ProductSearchResult | None:
    url = _clean_text(item.get("url"))
    image = _clean_text(item.get("image"))
    name = _clean_text(item.get("name"))
    if not url or not image or not name:
        return None  # need a real product page + image to be useful

    offers = item.get("offers") if isinstance(item.get("offers"), dict) else {}
    brand = item.get("brand") if isinstance(item.get("brand"), dict) else {}

    return ProductSearchResult(
        retailer=_retailer_from_url(url),
        name=name,
        url=url,
        category=category,
        image_url=image,
        price_cents=_price_to_cents(offers.get("price")),
        currency=_normalize_currency(offers.get("priceCurrency")),
        source="apify",
        metadata={"brand": _clean_text(brand.get("slogan")), "description": _clean_text(item.get("description"))},
    )


def _normalize_currency(value: Any) -> str:
    if isinstance(value, str):
        v = value.strip()
        if v in {"$", "US$", "USD"}:
            return "USD"
        if v:
            return v
    return "USD"


def product_search_provider_from_settings(settings: Settings | None = None) -> ProductSearchProvider:
    settings = settings or load_settings()
    if settings.product_search_provider == "apify":
        return ApifyEcommerceProvider(
            api_token=settings.apify_token or "",
            country_code=settings.google_shopping_gl or "us",
        )
    if settings.product_search_provider == "awin":
        catalog_path = settings.data_dir / "awin_catalog.sqlite3"
        return AWINProductSearchProvider(catalog_path)
    if settings.product_search_provider in {"google_shopping", "serpapi"}:
        return SerpApiGoogleShoppingProvider(
            api_key=settings.serpapi_api_key or "",
            location=settings.google_shopping_location,
            gl=settings.google_shopping_gl,
            hl=settings.google_shopping_hl,
        )
    if settings.product_search_provider == "tavily":
        return TavilyProductSearchProvider(api_key=settings.tavily_api_key or "")
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
        and is_apparel_result(result.name, result.retailer, result.url)
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
