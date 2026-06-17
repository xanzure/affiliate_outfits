from __future__ import annotations

import csv
import gzip
import io
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

_AWIN_API_BASE = "https://api.awin.com"


@dataclass(frozen=True)
class FeedInfo:
    feed_id: str
    merchant_id: str
    merchant_name: str
    url: str
    total_products: int


def list_feeds(publisher_id: str, oauth_token: str) -> list[FeedInfo]:
    """Return all product feeds available to this publisher."""
    url = f"{_AWIN_API_BASE}/publishers/{publisher_id}/feeds"
    req = Request(url, headers={"Authorization": f"Bearer {oauth_token}"})
    with urlopen(req, timeout=30) as resp:
        import json
        data = json.loads(resp.read())

    feeds = []
    for item in data:
        if item.get("status") != "active":
            continue
        feeds.append(FeedInfo(
            feed_id=str(item["id"]),
            merchant_id=str(item["merchantId"]),
            merchant_name=item.get("name", ""),
            url=item.get("url", ""),
            total_products=item.get("totalProducts", 0),
        ))
    return feeds


def _parse_price(raw: str) -> int | None:
    try:
        return int(float(raw.replace(",", "").strip()) * 100)
    except (ValueError, AttributeError):
        return None


# AWIN feed CSV column names vary slightly by merchant — these are the standard ones
_COL_ALIASES: dict[str, list[str]] = {
    "aw_product_id":  ["aw_product_id", "AWProductId", "product_id"],
    "merchant_id":    ["merchant_id", "MerchantId", "merchantId"],
    "merchant_name":  ["merchant_name", "MerchantName", "merchantName"],
    "product_name":   ["product_name", "ProductName", "name"],
    "brand_name":     ["brand_name", "BrandName", "brand"],
    "merchant_category": ["merchant_category", "MerchantCategory", "category"],
    "colour":         ["colour", "color", "Colour", "Color"],
    "search_price":   ["search_price", "SearchPrice", "price"],
    "currency":       ["currency", "Currency"],
    "aw_image_url":   ["aw_image_url", "AWImageUrl", "image_url"],
    "aw_deep_link":   ["aw_deep_link", "AWDeepLink", "deep_link", "affiliate_url"],
    "merchant_deep_link": ["merchant_deep_link", "MerchantDeepLink", "product_url"],
    "description":    ["description", "Description", "product_description"],
    "in_stock":       ["in_stock", "InStock", "stock"],
}


def _resolve(row: dict, key: str) -> str | None:
    for alias in _COL_ALIASES.get(key, [key]):
        if alias in row:
            return row[alias] or None
    return None


def _map_category(merchant_category: str | None) -> str | None:
    """Map AWIN merchant category strings to our internal categories."""
    if not merchant_category:
        return None
    mc = merchant_category.lower()
    if any(w in mc for w in ("shoe", "boot", "trainer", "sneaker", "footwear", "heel", "sandal")):
        return "shoe"
    if any(w in mc for w in ("jewel", "necklace", "ring", "bracelet", "earring")):
        return "jewelry"
    if any(w in mc for w in ("bag", "handbag", "purse", "tote", "clutch")):
        return "bag"
    if any(w in mc for w in ("hat", "cap", "beanie", "beret")):
        return "hat"
    if any(w in mc for w in ("sunglasses", "eyewear", "glasses")):
        return "sunglasses"
    if any(w in mc for w in ("dress",)):
        return "dress"
    if any(w in mc for w in ("top", "shirt", "blouse", "tee", "t-shirt", "sweater", "knitwear", "hoodie")):
        return "top"
    if any(w in mc for w in ("trouser", "pant", "jean", "denim", "shorts", "skirt")):
        return "bottom"
    if any(w in mc for w in ("jacket", "coat", "blazer", "outerwear")):
        return "outerwear"
    if any(w in mc for w in ("swim", "bikini", "swimwear")):
        return "swimwear"
    if any(w in mc for w in ("accessory", "accessories", "scarf", "belt", "sock", "glove")):
        return "accessory"
    return None


def download_and_ingest_feed(
    feed: FeedInfo,
    conn: sqlite3.Connection,
    *,
    oauth_token: str,
    batch_size: int = 500,
) -> int:
    """Download one feed and upsert all products. Returns count ingested."""
    from app.db.awin_catalog import upsert_catalog_product
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()

    logger.info("Downloading feed: %s (%s products)", feed.merchant_name, feed.total_products)

    req = Request(feed.url, headers={"Authorization": f"Bearer {oauth_token}"})
    with urlopen(req, timeout=120) as resp:
        raw = resp.read()

    # Feeds may be gzipped
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)

    text = raw.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))

    count = 0
    for csv_row in reader:
        product_id = _resolve(csv_row, "aw_product_id")
        affiliate_url = _resolve(csv_row, "aw_deep_link")
        product_name = _resolve(csv_row, "product_name")

        if not product_id or not affiliate_url or not product_name:
            continue

        merchant_category = _resolve(csv_row, "merchant_category")
        mapped_category = _map_category(merchant_category)

        row = {
            "aw_product_id":    product_id,
            "merchant_id":      _resolve(csv_row, "merchant_id") or feed.merchant_id,
            "merchant_name":    _resolve(csv_row, "merchant_name") or feed.merchant_name,
            "product_name":     product_name,
            "brand_name":       _resolve(csv_row, "brand_name"),
            "category":         mapped_category,
            "merchant_category": merchant_category,
            "colour":           _resolve(csv_row, "colour"),
            "price_cents":      _parse_price(_resolve(csv_row, "search_price") or ""),
            "currency":         _resolve(csv_row, "currency") or "GBP",
            "image_url":        _resolve(csv_row, "aw_image_url"),
            "affiliate_url":    affiliate_url,
            "product_url":      _resolve(csv_row, "merchant_deep_link"),
            "description":      _resolve(csv_row, "description"),
            "in_stock":         (_resolve(csv_row, "in_stock") or "1") not in ("0", "false", "False", "no"),
            "last_seen_at":     now,
        }
        upsert_catalog_product(conn, row)
        count += 1

        if count % batch_size == 0:
            conn.commit()
            logger.debug("  %d rows ingested", count)

    conn.commit()
    logger.info("  Done: %d products from %s", count, feed.merchant_name)
    return count


def sync_all_feeds(
    publisher_id: str,
    oauth_token: str,
    catalog_path: Path,
) -> dict[str, int]:
    """Sync all active feeds into the local catalog. Returns {merchant_name: count}."""
    from app.db.awin_catalog import connect_catalog

    conn = connect_catalog(catalog_path)
    feeds = list_feeds(publisher_id, oauth_token)
    logger.info("Found %d active feeds", len(feeds))

    results: dict[str, int] = {}
    for feed in feeds:
        if not feed.url:
            logger.warning("No URL for feed: %s", feed.merchant_name)
            continue
        try:
            count = download_and_ingest_feed(feed, conn, oauth_token=oauth_token)
            results[feed.merchant_name] = count
        except Exception:
            logger.exception("Failed to ingest feed: %s", feed.merchant_name)

    conn.close()
    return results
