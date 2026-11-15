#!/usr/bin/env python3
"""
Manual outfit ingestion from curated product URLs.

Input file format (see data/sample_outfits.txt):
──────────────────────────────────────────────────
CONCEPT: Bad Bunny Concert

OUTFIT 1
https://www.revolve.com/...
https://www.asos.com/...
https://www.freepeople.com/...

OUTFIT 2
https://...
https://...
──────────────────────────────────────────────────

Usage:
    python scripts/ingest_outfits.py data/sample_outfits.txt
    python scripts/ingest_outfits.py data/sample_outfits.txt --dry-run   # scrape only, no DB writes
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# ── scraping ──────────────────────────────────────────────────────────────────

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

_CATEGORY_KEYWORDS: list[tuple[str, str]] = [
    ("jacket", "jacket"), ("blazer", "blazer"), ("coat", "coat"),
    ("cardigan", "cardigan"), ("vest", "vest"), ("puffer", "puffer"),
    ("sweater", "sweater"), ("knit", "knit"), ("turtleneck", "turtleneck"),
    ("hoodie", "top"), ("sweatshirt", "top"), ("blouse", "blouse"),
    ("shirt", "shirt"), ("top", "top"), ("tank", "tank"), ("tee", "tee"),
    ("crop", "top"), ("polo", "polo"),
    ("dress", "dress"), ("jumpsuit", "jumpsuit"), ("romper", "romper"),
    ("skirt", "skirt"), ("mini", "dress"), ("maxi", "dress"),
    ("jeans", "jeans"), ("denim", "jeans"), ("trousers", "trousers"),
    ("pants", "pants"), ("shorts", "shorts"), ("leggings", "leggings"),
    ("boot", "boots"), ("sneaker", "sneakers"), ("loafer", "loafers"),
    ("sandal", "sandals"), ("heel", "heels"), ("mule", "shoes"),
    ("shoe", "shoes"), ("flat", "shoes"), ("oxford", "shoes"),
    ("bag", "bag"), ("tote", "bag"), ("clutch", "bag"), ("purse", "bag"),
    ("backpack", "bag"), ("crossbody", "bag"), ("satchel", "bag"),
    ("belt", "belt"), ("scarf", "scarf"), ("hat", "hat"), ("cap", "hat"),
    ("necklace", "necklace"), ("earring", "earrings"), ("bracelet", "bracelet"),
    ("ring", "ring"), ("watch", "watch"), ("sunglasses", "sunglasses"),
]


@dataclass
class ScrapedProduct:
    url: str
    name: str
    price_cents: int | None
    currency: str
    image_url: str | None
    category: str | None
    retailer: str


def scrape_product(url: str) -> ScrapedProduct:
    """Scrape product info from a retail page using JSON-LD and meta tags."""
    retailer = urlparse(url).hostname or url
    retailer = re.sub(r"^www\.", "", retailer).split(".")[0]

    html = _fetch_html(url)
    name = _extract_name(html)
    price_cents, currency = _extract_price(html)
    image_url = _extract_image(html, url)
    category = _guess_category(name or "")

    return ScrapedProduct(
        url=url,
        name=name or f"Product from {retailer}",
        price_cents=price_cents,
        currency=currency,
        image_url=image_url,
        category=category,
        retailer=retailer,
    )


def _fetch_html(url: str) -> str:
    """Fetch page HTML, using Playwright if available (handles JS-heavy retail sites)."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent=_HEADERS["User-Agent"],
                locale="en-US",
            )
            page = ctx.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            # Wait a moment for any lazy JSON-LD to render
            page.wait_for_timeout(1500)
            html = page.content()
            browser.close()
            return html
    except ImportError:
        pass

    # Fallback: plain HTTP (works for simpler sites)
    req = Request(url, headers=_HEADERS)
    try:
        with urlopen(req, timeout=20) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        raise RuntimeError(f"Failed to fetch {url}: {e}") from e


def _extract_name(html: str) -> str | None:
    # JSON-LD first
    for block in re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S):
        try:
            data = json.loads(block)
            items = data if isinstance(data, list) else [data]
            for item in items:
                if isinstance(item, dict) and item.get("@type") in ("Product", "product"):
                    name = item.get("name")
                    if name:
                        return str(name).strip()
        except Exception:
            pass

    # OG / meta fallbacks
    for pattern in [
        r'<meta[^>]*property="og:title"[^>]*content="([^"]+)"',
        r'<meta[^>]*name="title"[^>]*content="([^"]+)"',
        r'<title[^>]*>([^<]+)</title>',
    ]:
        m = re.search(pattern, html, re.I)
        if m:
            title = m.group(1).strip()
            # Strip common site-name suffixes
            title = re.sub(r'\s*[|\-–]\s*\w[\w\s]{0,30}$', '', title).strip()
            if title:
                return title

    return None


def _extract_price(html: str) -> tuple[int | None, str]:
    currency = "USD"

    # JSON-LD
    for block in re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S):
        try:
            data = json.loads(block)
            items = data if isinstance(data, list) else [data]
            for item in items:
                if not isinstance(item, dict):
                    continue
                offers = item.get("offers") or item.get("Offers")
                if isinstance(offers, dict):
                    offers = [offers]
                if isinstance(offers, list) and offers:
                    o = offers[0]
                    price = o.get("price") or o.get("lowPrice")
                    cur = o.get("priceCurrency", "USD")
                    if price is not None:
                        try:
                            cents = int(round(float(str(price).replace(",", "")) * 100))
                            return cents, cur
                        except ValueError:
                            pass
        except Exception:
            pass

    # Meta / OG price
    for pattern in [
        r'<meta[^>]*property="product:price:amount"[^>]*content="([^"]+)"',
        r'<meta[^>]*property="og:price:amount"[^>]*content="([^"]+)"',
        r'"price"\s*:\s*"?(\d+\.?\d*)"?',
    ]:
        m = re.search(pattern, html, re.I)
        if m:
            try:
                cents = int(round(float(m.group(1).replace(",", "")) * 100))
                return cents, currency
            except ValueError:
                pass

    return None, currency


def _extract_image(html: str, page_url: str) -> str | None:
    # JSON-LD image
    for block in re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S):
        try:
            data = json.loads(block)
            items = data if isinstance(data, list) else [data]
            for item in items:
                if not isinstance(item, dict) or item.get("@type") not in ("Product", "product"):
                    continue
                img = item.get("image")
                if isinstance(img, list):
                    img = img[0]
                if isinstance(img, dict):
                    img = img.get("url")
                if img and isinstance(img, str):
                    return img
        except Exception:
            pass

    # OG image
    m = re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"', html, re.I)
    if m:
        return m.group(1).strip()

    # twitter:image
    m = re.search(r'<meta[^>]*name="twitter:image"[^>]*content="([^"]+)"', html, re.I)
    if m:
        return m.group(1).strip()

    return None


def _guess_category(name: str) -> str | None:
    lower = name.lower()
    for keyword, category in _CATEGORY_KEYWORDS:
        if keyword in lower:
            return category
    return None


# ── input file parsing ────────────────────────────────────────────────────────

@dataclass
class OutfitSpec:
    number: int
    urls: list[str] = field(default_factory=list)


@dataclass
class ConceptSpec:
    name: str
    outfits: list[OutfitSpec] = field(default_factory=list)


def parse_input_file(path: Path) -> list[ConceptSpec]:
    concepts: list[ConceptSpec] = []
    current_concept: ConceptSpec | None = None
    current_outfit: OutfitSpec | None = None

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.upper().startswith("CONCEPT:"):
            if current_concept:
                if current_outfit and current_outfit.urls:
                    current_concept.outfits.append(current_outfit)
                concepts.append(current_concept)
            name = line.split(":", 1)[1].strip()
            current_concept = ConceptSpec(name=name)
            current_outfit = None

        elif re.match(r"^OUTFIT\s+\d+", line, re.I):
            if current_concept is None:
                raise ValueError(f"OUTFIT line before any CONCEPT: {line!r}")
            if current_outfit and current_outfit.urls:
                current_concept.outfits.append(current_outfit)
            num = int(re.search(r"\d+", line).group())
            current_outfit = OutfitSpec(number=num)

        elif line.startswith("http"):
            if current_outfit is None:
                raise ValueError(f"URL before any OUTFIT: {line!r}")
            current_outfit.urls.append(line.split()[0])  # strip any trailing comment

    # flush last
    if current_concept:
        if current_outfit and current_outfit.urls:
            current_concept.outfits.append(current_outfit)
        if current_concept.outfits:
            concepts.append(current_concept)

    return concepts


# ── pipeline ──────────────────────────────────────────────────────────────────

def run_ingestion(input_path: Path, *, dry_run: bool = False) -> None:
    from app.agents.collage.style_agent import generate_batch_visual_style
    from app.db.collages import create_collage
    from app.db.concepts import upsert_concept
    from app.db.outfits import create_outfit, update_outfit_spec
    from app.db.pg_connection import connect_postgres
    from app.db.products import upsert_product
    from app.pipelines.collage_pipeline import render_collage_manifest_for_images
    from app.pipelines.image_pipeline import prepare_product_images
    from app.services.image_service import ImageService

    concepts = parse_input_file(input_path)
    if not concepts:
        log.error("No concepts found in %s", input_path)
        sys.exit(1)

    log.info("Parsed %d concept(s) from %s", len(concepts), input_path)
    for c in concepts:
        log.info("  '%s' → %d outfit(s)", c.name, len(c.outfits))
        for o in c.outfits:
            log.info("    Outfit %d: %d URLs", o.number, len(o.urls))

    if dry_run:
        log.info("\n-- DRY RUN: scraping only, no DB writes --\n")

    conn = None if dry_run else connect_postgres("")
    image_service = ImageService()

    for concept_spec in concepts:
        log.info("\n═══ CONCEPT: %s ═══", concept_spec.name)

        if not dry_run:
            concept = upsert_concept(conn, concept_spec.name, source="manual")
            log.info("Concept ID: %s", concept.id)
        else:
            concept = None

        # One visual style for the whole concept batch
        batch_style = None if dry_run else generate_batch_visual_style(concept_spec.name)
        if batch_style:
            log.info("Visual style: %s (bg=%s)", batch_style.palette_name, batch_style.background_hex)

        for outfit_spec in concept_spec.outfits:
            log.info("\n  ── Outfit %d ──", outfit_spec.number)
            scraped: list[ScrapedProduct] = []

            for url in outfit_spec.urls:
                log.info("  Scraping: %s", url[:80])
                try:
                    product = scrape_product(url)
                    scraped.append(product)
                    price_str = f"${product.price_cents/100:.2f}" if product.price_cents else "?"
                    log.info("    ✓ %s | %s | cat=%s | img=%s",
                             product.name[:50], price_str, product.category,
                             "yes" if product.image_url else "NO IMAGE")
                except Exception as e:
                    log.warning("    ✗ Failed to scrape %s: %s", url[:60], e)
                time.sleep(0.5)  # polite delay between requests

            if not scraped:
                log.warning("  No products scraped for outfit %d, skipping", outfit_spec.number)
                continue

            if dry_run:
                continue

            # Upsert products
            products = []
            for s in scraped:
                p = upsert_product(
                    conn,
                    retailer=s.retailer,
                    name=s.name,
                    url=s.url,
                    category=s.category,
                    image_url=s.image_url,
                    price_cents=s.price_cents,
                    currency=s.currency,
                )
                products.append(p)
                log.info("  Product saved: %s", p.id)

            # Download, rembg, upload to Supabase Storage
            log.info("  Processing images...")
            prepared_images = prepare_product_images(conn, products, image_service=image_service)

            # Build outfit spec
            outfit_items = []
            for s, p in zip(scraped, products):
                outfit_items.append({
                    "name": p.name,
                    "category": p.category or "item",
                    "url": p.url,
                    "product_id": p.id,
                })
            outfit_spec_dict = {
                "concept": concept_spec.name,
                "outfit_number": outfit_spec.number,
                "items": outfit_items,
                "source": "manual",
            }

            outfit = create_outfit(
                conn,
                concept_id=concept.id,
                concept_seed=concept_spec.name,
                spec=outfit_spec_dict,
                product_ids=[p.id for p in products],
                metadata={"source": "manual_ingest"},
            )
            log.info("  Outfit saved: %s", outfit.id)

            # Generate collage
            log.info("  Rendering collage...")
            categories = [p.category for p in products]
            collage_export = render_collage_manifest_for_images(
                prepared_images,
                output_name=f"{outfit.id}.png",
                style=batch_style,
                concept_name=concept_spec.name,
                outfit_number=outfit_spec.number,
                categories=categories,
            )

            # Add product_ids to manifest pieces
            manifest = dict(collage_export.manifest)
            pieces = []
            for piece, product in zip(manifest["pieces"], products):
                pieces.append({**piece, "product_id": product.id})
            manifest["pieces"] = pieces

            collage = create_collage(
                conn,
                outfit_id=outfit.id,
                image_path=str(collage_export.image_path),
                layout=manifest,
                metadata={
                    "renderer": "scattered",
                    "source": "manual_ingest",
                    **({"background_hex": batch_style.background_hex,
                        "accent_hex": batch_style.accent_hex,
                        "font_style": batch_style.font_style,
                        "palette_name": batch_style.palette_name} if batch_style else {}),
                },
            )

            # Write layout back to outfit spec for website
            from app.pipelines.daily_pipeline import _spec_with_website_layout
            outfit = update_outfit_spec(
                conn,
                outfit.id,
                _spec_with_website_layout(outfit.spec, collage.layout),
            )

            log.info("  Collage: %s", collage_export.image_path)
            log.info("  ✓ Outfit %d complete", outfit_spec.number)

    log.info("\n✓ Ingestion complete")


# ── entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest curated outfit links into the pipeline")
    parser.add_argument("input", type=Path, help="Path to an outfits file (see data/sample_outfits.txt)")
    parser.add_argument("--dry-run", action="store_true", help="Scrape only, no DB writes")
    args = parser.parse_args()

    if not args.input.exists():
        log.error("File not found: %s", args.input)
        sys.exit(1)

    run_ingestion(args.input, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
