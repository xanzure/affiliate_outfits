from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.config import PROJECT_ROOT, Settings, load_settings


SCHEMA_PATH = PROJECT_ROOT / "app/db/schema.sql"


def connect(database_path: Path) -> sqlite3.Connection:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_database(database_path: Path) -> None:
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    with connect(database_path) as conn:
        _prepare_legacy_concept_migration(conn)
        conn.executescript(schema)
        _copy_legacy_concept_migration(conn)
        conn.commit()


class StorageService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or load_settings()
        self.database_path = self.settings.database_path

    def initialize(self) -> None:
        initialize_database(self.database_path)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = connect(self.database_path)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def _prepare_legacy_concept_migration(conn: sqlite3.Connection) -> None:
    tables = _table_names(conn)
    if "outfits" in tables and "concept_id" not in _column_names(conn, "outfits"):
        conn.execute("ALTER TABLE outfits RENAME TO outfits_legacy_prompts")

    if "posts" in tables and "concept_id" not in _column_names(conn, "posts"):
        conn.execute("ALTER TABLE posts RENAME TO posts_legacy_prompts")

    tables = _table_names(conn)
    if (
        "metrics" in tables
        and "metrics_legacy_posts" not in tables
        and "posts" not in _foreign_key_tables(conn, "metrics")
    ):
        conn.execute("ALTER TABLE metrics RENAME TO metrics_legacy_posts")


def _copy_legacy_concept_migration(conn: sqlite3.Connection) -> None:
    tables = _table_names(conn)
    if "prompts" in tables:
        conn.execute(
            """
            INSERT OR IGNORE INTO concepts (
                id, seed, status, source, usage_count, ranking_score,
                last_posted_date_est, created_at, updated_at, metadata_json
            )
            SELECT
                id,
                text,
                CASE WHEN status = 'retired' THEN 'retired' ELSE 'active' END,
                source,
                usage_count,
                50,
                NULL,
                created_at,
                updated_at,
                metadata_json
            FROM prompts
            """
        )

    if "outfits_legacy_prompts" in tables:
        conn.execute(
            """
            INSERT OR IGNORE INTO outfits (
                id, concept_id, concept_seed, spec_json, product_ids_json,
                created_at, metadata_json
            )
            SELECT
                id, prompt_id, prompt_text, spec_json, product_ids_json,
                created_at, metadata_json
            FROM outfits_legacy_prompts
            """
        )

    if "posts_legacy_prompts" in tables:
        conn.execute(
            """
            INSERT OR IGNORE INTO posts (
                id, concept_id, outfit_id, platform, status, image_path, caption,
                platform_post_id, published_at, created_at, updated_at, metadata_json
            )
            SELECT
                id, prompt_id, outfit_id, platform, status, image_path, caption,
                platform_post_id, published_at, created_at, updated_at, metadata_json
            FROM posts_legacy_prompts
            """
        )

    if "metrics_legacy_posts" in tables:
        conn.execute(
            """
            INSERT OR IGNORE INTO metrics (
                id, post_id, platform, collected_at, views, likes, comments,
                shares, saves, clicks, score, metadata_json
            )
            SELECT
                id, post_id, platform, collected_at, views, likes, comments,
                shares, saves, clicks, score, metadata_json
            FROM metrics_legacy_posts
            WHERE EXISTS (
                SELECT 1 FROM posts WHERE posts.id = metrics_legacy_posts.post_id
            )
            """
        )


def _table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {row["name"] for row in rows}


def _column_names(conn: sqlite3.Connection, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row["name"] for row in rows}


def _foreign_key_tables(conn: sqlite3.Connection, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA foreign_key_list({table_name})").fetchall()
    return {row["table"] for row in rows}
