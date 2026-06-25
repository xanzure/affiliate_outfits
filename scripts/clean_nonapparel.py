#!/usr/bin/env python3
"""Delete cached products that aren't apparel (raw fabric, craft supplies,
furniture, home goods) — the junk material-word searches dragged in.

Uses the same is_apparel_result filter the search now applies, so this clears
what already leaked through. Products referenced by an outfit are never touched.

Usage:
    python scripts/clean_nonapparel.py            # dry-run: list what would go
    python scripts/clean_nonapparel.py --apply    # actually delete
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json

from app.db.pg_connection import connect_postgres
from app.db.products import list_products
from app.services.product_search_service import is_apparel_result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually delete (default is dry-run)")
    args = ap.parse_args()

    conn = connect_postgres("")

    # never delete a product that's used in an outfit
    referenced: set[str] = set()
    for row in conn.execute("SELECT product_ids_json FROM outfits").fetchall():
        try:
            referenced.update(json.loads(row["product_ids_json"] or "[]"))
        except Exception:
            pass

    junk = [
        p for p in list_products(conn)
        if p.id not in referenced and not is_apparel_result(p.name, p.retailer, p.url)
    ]

    print(f"{len(junk)} non-apparel product(s) to remove "
          f"({'APPLYING' if args.apply else 'dry-run'}):\n")
    for p in junk:
        print(f"  {p.retailer[:16]:16} | {str(p.name)[:50]}")

    if not args.apply:
        print("\nDry-run only. Re-run with --apply to delete.")
        conn.close()
        return

    storage = None
    try:
        from app.services.asset_storage import asset_storage_from_env
        storage = asset_storage_from_env()
    except Exception:
        pass

    deleted = 0
    for p in junk:
        # best-effort: remove the processed cutout from storage
        if storage and p.image_url and "supabase.co/storage" in (p.image_url or ""):
            try:
                storage.remove_product_image(p.id)  # type: ignore[attr-defined]
            except Exception:
                pass
        conn.execute("DELETE FROM products WHERE id = ?", (p.id,))
        deleted += 1

    print(f"\nDeleted {deleted} non-apparel product(s).")
    conn.close()


if __name__ == "__main__":
    main()
