from __future__ import annotations

import sqlite3

from app.db._helpers import dumps_json, loads_json, new_id, require_row, utc_now
from app.db.models import JsonDict, Platform, Post, PostStatus


def _to_post(row: sqlite3.Row) -> Post:
    return Post(
        id=row["id"],
        concept_id=row["concept_id"],
        outfit_id=row["outfit_id"],
        platform=row["platform"],
        status=row["status"],
        image_path=row["image_path"],
        caption=row["caption"],
        platform_post_id=row["platform_post_id"],
        published_at=row["published_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        metadata=loads_json(row["metadata_json"], {}),
    )


def create_post(
    conn: sqlite3.Connection,
    *,
    platform: Platform,
    concept_id: str | None = None,
    outfit_id: str | None = None,
    image_path: str | None = None,
    caption: str | None = None,
    status: PostStatus = "draft",
    platform_post_id: str | None = None,
    published_at: str | None = None,
    metadata: JsonDict | None = None,
    post_id: str | None = None,
) -> Post:
    now = utc_now()
    post_id = post_id or new_id("post")
    conn.execute(
        """
        INSERT INTO posts (
            id, concept_id, outfit_id, platform, status, image_path, caption,
            platform_post_id, published_at, created_at, updated_at, metadata_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            post_id,
            concept_id,
            outfit_id,
            platform,
            status,
            image_path,
            caption,
            platform_post_id,
            published_at,
            now,
            now,
            dumps_json(metadata or {}),
        ),
    )
    return get_post(conn, post_id)


def get_post(conn: sqlite3.Connection, post_id: str) -> Post:
    row = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    return _to_post(require_row(row, "post", post_id))


def update_post_status(
    conn: sqlite3.Connection,
    post_id: str,
    *,
    status: PostStatus,
    platform_post_id: str | None = None,
    published_at: str | None = None,
) -> Post:
    now = utc_now()
    conn.execute(
        """
        UPDATE posts
        SET status = ?,
            platform_post_id = COALESCE(?, platform_post_id),
            published_at = COALESCE(?, published_at),
            updated_at = ?
        WHERE id = ?
        """,
        (status, platform_post_id, published_at, now, post_id),
    )
    return get_post(conn, post_id)


def update_post_metadata(
    conn: sqlite3.Connection,
    post_id: str,
    metadata: JsonDict,
) -> Post:
    now = utc_now()
    existing = get_post(conn, post_id)
    conn.execute(
        """
        UPDATE posts
        SET metadata_json = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (dumps_json({**existing.metadata, **metadata}), now, post_id),
    )
    return get_post(conn, post_id)


def list_posts(conn: sqlite3.Connection, *, status: PostStatus | None = None) -> list[Post]:
    if status:
        rows = conn.execute(
            "SELECT * FROM posts WHERE status = ? ORDER BY created_at DESC",
            (status,),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM posts ORDER BY created_at DESC").fetchall()
    return [_to_post(row) for row in rows]


def list_posts_for_concept(conn: sqlite3.Connection, concept_id: str) -> list[Post]:
    rows = conn.execute(
        "SELECT * FROM posts WHERE concept_id = ? ORDER BY created_at DESC",
        (concept_id,),
    ).fetchall()
    return [_to_post(row) for row in rows]
