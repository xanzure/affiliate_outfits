#!/usr/bin/env python3
"""
Idempotent schema migration for the admin dashboard.

Adds scheduling columns to `posts` and creates the `jobs` and `admin_actions`
tables. Safe to run repeatedly. Targets the live Supabase Postgres DB.

Usage:
  python scripts/migrate_dashboard.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.pg_connection import connect_postgres

STATEMENTS = [
    # products: soft-delete (archived = out of cache, kept so outfits don't break)
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS archived_at TEXT",
    "CREATE INDEX IF NOT EXISTS idx_products_archived_at ON products(archived_at)",
    # posts: scheduling + approval + link-health columns
    "ALTER TABLE posts ADD COLUMN IF NOT EXISTS scheduled_for TEXT",
    "ALTER TABLE posts ADD COLUMN IF NOT EXISTS queue_order TEXT",
    "ALTER TABLE posts ADD COLUMN IF NOT EXISTS is_manual_schedule BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE posts ADD COLUMN IF NOT EXISTS approved BOOLEAN NOT NULL DEFAULT TRUE",
    "ALTER TABLE posts ADD COLUMN IF NOT EXISTS link_check TEXT",
    "UPDATE posts SET queue_order = created_at WHERE queue_order IS NULL",
    "CREATE INDEX IF NOT EXISTS idx_posts_scheduled_for ON posts(scheduled_for)",
    "CREATE INDEX IF NOT EXISTS idx_posts_queue_order ON posts(queue_order)",
    # jobs: pipeline trigger queue
    """
    CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY,
        type TEXT NOT NULL,
        payload_json TEXT NOT NULL DEFAULT '{}',
        status TEXT NOT NULL DEFAULT 'queued',
        result_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)",
    # admin_actions: lightweight audit log
    """
    CREATE TABLE IF NOT EXISTS admin_actions (
        id TEXT PRIMARY KEY,
        action TEXT NOT NULL,
        target_id TEXT,
        detail_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_admin_actions_created_at ON admin_actions(created_at)",
]


def main() -> None:
    conn = connect_postgres("")
    for stmt in STATEMENTS:
        sql = stmt.strip()
        label = sql.split("\n")[0][:60]
        try:
            conn.execute(sql)
            print(f"OK   {label}")
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL {label}\n     {exc}")
    conn.close()
    print("migration complete")


if __name__ == "__main__":
    main()
