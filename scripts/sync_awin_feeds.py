#!/usr/bin/env python3
"""
Download all approved AWIN product feeds into the local catalog.

Usage:
  python scripts/sync_awin_feeds.py            # sync all feeds
  python scripts/sync_awin_feeds.py --stats    # show catalog stats only
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("sync_awin_feeds")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stats", action="store_true", help="Print catalog stats and exit")
    args = parser.parse_args()

    from app.config import load_settings
    from app.db.awin_catalog import catalog_stats, connect_catalog

    settings = load_settings()
    catalog_path = settings.data_dir / "awin_catalog.sqlite3"

    if args.stats:
        conn = connect_catalog(catalog_path)
        stats = catalog_stats(conn)
        conn.close()
        print(f"Total products : {stats['total_products']:,}")
        print(f"Merchants      : {stats['merchants']}")
        print(f"In stock       : {stats['in_stock']:,}")
        return

    if not settings.awin_publisher_id:
        log.error("AWIN_PUBLISHER_ID not set in .env")
        sys.exit(1)
    if not settings.awin_oauth2_token:
        log.error("AWIN_OAUTH2_TOKEN not set in .env")
        sys.exit(1)

    from app.services.awin_feed_service import sync_all_feeds

    log.info("Syncing AWIN feeds → %s", catalog_path)
    results = sync_all_feeds(
        publisher_id=settings.awin_publisher_id,
        oauth_token=settings.awin_oauth2_token,
        catalog_path=catalog_path,
    )

    total = sum(results.values())
    log.info("Done. %d products across %d merchants", total, len(results))
    for merchant, count in sorted(results.items(), key=lambda x: -x[1]):
        log.info("  %-40s %6d products", merchant, count)


if __name__ == "__main__":
    main()
