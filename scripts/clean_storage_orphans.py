#!/usr/bin/env python3
"""Delete orphaned files in Supabase Storage — product/collage images whose
DB row no longer exists (e.g. after removing non-apparel junk).

Usage:
    python scripts/clean_storage_orphans.py            # dry-run: count orphans
    python scripts/clean_storage_orphans.py --apply    # delete them
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.pg_connection import connect_postgres
from app.services.asset_storage import asset_storage_from_env


def _list_all(sb, bucket: str, folder: str) -> list[str]:
    names, offset = [], 0
    while True:
        batch = sb.storage.from_(bucket).list(
            folder, {"limit": 1000, "offset": offset}
        )
        if not batch:
            break
        names.extend(f["name"] for f in batch if f.get("name"))
        if len(batch) < 1000:
            break
        offset += 1000
    return names


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually delete (default dry-run)")
    args = ap.parse_args()

    storage = asset_storage_from_env()
    if storage is None:
        print("Supabase storage not configured (SUPABASE_URL / SERVICE_ROLE_KEY).")
        return
    sb = storage._sb  # service-role client

    conn = connect_postgres("")
    product_ids = {r["id"] for r in conn.execute("SELECT id FROM products").fetchall()}
    collage_ids = {r["id"] for r in conn.execute("SELECT id FROM collages").fetchall()}
    conn.close()

    targets = [
        ("product-images", "products", product_ids),
        ("collages", "collages", collage_ids),
    ]
    grand_total = 0
    for bucket, folder, live_ids in targets:
        files = _list_all(sb, bucket, folder)
        orphans = [f for f in files if f.removesuffix(".png") not in live_ids]
        print(f"[{bucket}/{folder}] {len(files)} files, {len(orphans)} orphaned")
        for name in orphans[:10]:
            print(f"    {name}")
        if len(orphans) > 10:
            print(f"    ... and {len(orphans) - 10} more")
        grand_total += len(orphans)
        if args.apply and orphans:
            paths = [f"{folder}/{name}" for name in orphans]
            for i in range(0, len(paths), 100):
                sb.storage.from_(bucket).remove(paths[i:i + 100])
            print(f"    deleted {len(paths)} file(s)")

    if not args.apply:
        print(f"\nDry-run: {grand_total} orphan(s). Re-run with --apply to delete.")
    else:
        print(f"\nDeleted {grand_total} orphaned storage file(s).")


if __name__ == "__main__":
    main()
