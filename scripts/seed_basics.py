#!/usr/bin/env python3
"""Seed the product cache with a list of basics so outfits can build on them.

Reads a text file, one item per line, pipe-delimited:

    category | query
    category | color | query

- Lines starting with # and blank lines are ignored.
- If color is omitted, it's auto-extracted from the query.
- `category` sets the product's zone for cache matching (top/bottom/shoe/bag/
  outerwear/dress/accessory or any descriptor that resolves to one).

Each item is searched (Apify), the best product stored, and its image processed
(Runflow cutout -> Supabase) so it becomes a reusable cached basic.

Usage:
    python scripts/seed_basics.py data/basics.txt            # source + process
    python scripts/seed_basics.py data/basics.txt --dry-run  # preview + cost only
    python scripts/seed_basics.py data/basics.txt --force    # re-source even if cached
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.collage.export import _resolve_zone
from app.config import load_settings
from app.db.pg_connection import connect_postgres
from app.pipelines.image_pipeline import prepare_product_images
from app.pipelines.product_pipeline import ProductSearchSpec, resolve_products_from_searches
from app.services.image_service import ImageService
from app.services.product_cache import extract_color_word, find_cached_match

_BATCH = 6                    # parallel searches per batch (avoid concurrency limits)
_EST_COST_PER_ITEM = 0.07     # conservative $/usable piece (see cost notes)


def _parse_line(line: str) -> tuple[str | None, str | None, str | None, str]:
    """Parse a pipe-delimited line. The QUERY is always the last column; the
    leading columns are category, color, material (in that order) as available:

        query
        category | query
        category | color | query
        category | color | material | query
    """
    parts = [p.strip() for p in line.split("|")]
    query = parts[-1]
    category = parts[0] if len(parts) >= 2 else None
    color = parts[1] if len(parts) >= 3 else None
    material = parts[2] if len(parts) >= 4 else None
    return category or None, color or None, material or None, query


def _chunks(items: list, n: int):
    for i in range(0, len(items), n):
        yield items[i:i + n]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("file", help="text file of basics (category | [color |] query per line)")
    ap.add_argument("--dry-run", action="store_true", help="preview parse + cost, source nothing")
    ap.add_argument("--force", action="store_true", help="source even if a near-match is already cached")
    args = ap.parse_args()

    settings = load_settings()
    if settings.product_search_provider != "apify":
        print(f"WARNING: PRODUCT_SEARCH_PROVIDER={settings.product_search_provider} (expected apify)")

    raw_lines = [
        ln.strip() for ln in Path(args.file).read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    print(f"{len(raw_lines)} item(s) in {args.file}")

    conn = connect_postgres("")
    specs: list[ProductSearchSpec] = []
    skipped = 0
    for line in raw_lines:
        category, color, material, query = _parse_line(line)
        if not query:
            continue
        color = color or extract_color_word(query)
        if not args.force:
            existing = find_cached_match(
                conn,
                zone=_resolve_zone(category or query),
                color=color,
                descriptor=f"{category or ''} {query}",
            )
            if existing:
                print(f"  SKIP cached: {query[:48]:48} -> {existing.name[:40]}")
                skipped += 1
                continue
        specs.append(ProductSearchSpec(
            query=query, category=category, color=color, material=material, limit=3,
        ))

    print(f"\n{len(specs)} to source, {skipped} skipped (already cached)")
    print(f"est. cost: ~${len(specs) * _EST_COST_PER_ITEM:.2f} (conservative)\n")

    if args.dry_run:
        for s in specs:
            print(f"  WILL SOURCE [{s.category or '?'}] ({s.color or '?'}): {s.query}")
        conn.close()
        return

    image_service = ImageService(settings)
    total_sourced = total_ready = 0
    for n, batch in enumerate(_chunks(specs, _BATCH), start=1):
        print(f"-- batch {n} ({len(batch)} item(s)) --", flush=True)
        products = resolve_products_from_searches(
            conn, batch, tracking_id="seed-basics", settings=settings,
        )
        prepared = prepare_product_images(conn, products, image_service=image_service)
        total_sourced += len(products)
        total_ready += len(prepared)
        print(f"   sourced {len(products)}, image-ready {len(prepared)}", flush=True)

    print(f"\nDone: {total_sourced} sourced, {total_ready} image-ready cached basics.")
    conn.close()


if __name__ == "__main__":
    main()
