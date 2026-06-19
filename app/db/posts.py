from __future__ import annotations

import sqlite3

from app.db._helpers import dumps_json, loads_json, new_id, require_row, utc_now
from app.db.models import JsonDict, Platform, Post, PostStatus


def _row_get(row: object, key: str, default: object = None) -> object:
    """Read a column from either a sqlite3.Row or a dict-like cursor row."""
    try:
        value = row[key]  # type: ignore[index]
    except (KeyError, IndexError):
        return default
    return default if value is None else value


def _to_bool(value: object) -> bool:
    return bool(value) and value not in (0, "0", "false", "False")


def _to_post(row: sqlite3.Row) -> Post:
    link_check_raw = _row_get(row, "link_check")
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
        scheduled_for=_row_get(row, "scheduled_for"),
        queue_order=_row_get(row, "queue_order"),
        is_manual_schedule=_to_bool(_row_get(row, "is_manual_schedule", False)),
        approved=_to_bool(_row_get(row, "approved", True)),
        link_check=loads_json(link_check_raw, None) if link_check_raw else None,
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
    scheduled_for: str | None = None,
    queue_order: str | None = None,
    is_manual_schedule: bool = False,
    approved: bool = False,
    metadata: JsonDict | None = None,
    post_id: str | None = None,
) -> Post:
    now = utc_now()
    post_id = post_id or new_id("post")
    conn.execute(
        """
        INSERT INTO posts (
            id, concept_id, outfit_id, platform, status, image_path, caption,
            platform_post_id, published_at, scheduled_for, queue_order,
            is_manual_schedule, approved, created_at, updated_at, metadata_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            scheduled_for,
            queue_order or now,
            is_manual_schedule,
            approved,
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


# ── dashboard scheduling helpers ─────────────────────────────────────────────

def approve_post(conn: sqlite3.Connection, post_id: str) -> Post:
    """Move a needs-approval draft into the FIFO queue."""
    conn.execute(
        "UPDATE posts SET approved = ?, updated_at = ? WHERE id = ?",
        (True, utc_now(), post_id),
    )
    return get_post(conn, post_id)


def schedule_post(
    conn: sqlite3.Connection,
    post_id: str,
    *,
    scheduled_for: str,
    is_manual: bool = True,
) -> Post:
    """Pin a post to a specific time (manual override bypasses the FIFO queue)."""
    conn.execute(
        """
        UPDATE posts
        SET status = 'scheduled', scheduled_for = ?, is_manual_schedule = ?,
            approved = ?, updated_at = ?
        WHERE id = ?
        """,
        (scheduled_for, is_manual, True, utc_now(), post_id),
    )
    return get_post(conn, post_id)


def cancel_schedule(conn: sqlite3.Connection, post_id: str) -> Post:
    """Unschedule a post and send it to the back of the queue."""
    now = utc_now()
    conn.execute(
        """
        UPDATE posts
        SET status = 'draft', scheduled_for = NULL, is_manual_schedule = ?,
            queue_order = ?, updated_at = ?
        WHERE id = ?
        """,
        (False, now, now, post_id),
    )
    return get_post(conn, post_id)


def update_post_caption(conn: sqlite3.Connection, post_id: str, caption: str) -> Post:
    conn.execute(
        "UPDATE posts SET caption = ?, updated_at = ? WHERE id = ?",
        (caption, utc_now(), post_id),
    )
    return get_post(conn, post_id)


def delete_post(conn: sqlite3.Connection, post_id: str) -> None:
    """Hard-delete a post. Only permitted before it has been published."""
    post = get_post(conn, post_id)
    if post.status == "published":
        raise ValueError("cannot delete a published post")
    conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))


def set_link_check(conn: sqlite3.Connection, post_id: str, result: JsonDict) -> Post:
    conn.execute(
        "UPDATE posts SET link_check = ?, updated_at = ? WHERE id = ?",
        (dumps_json(result), utc_now(), post_id),
    )
    return get_post(conn, post_id)


def list_queued_posts(conn: sqlite3.Connection, platform: Platform) -> list[Post]:
    """Approved, unscheduled posts of one platform, in FIFO order."""
    rows = conn.execute(
        """
        SELECT * FROM posts
        WHERE platform = ? AND status = 'draft' AND approved = ?
              AND scheduled_for IS NULL
        ORDER BY queue_order ASC
        """,
        (platform, True),
    ).fetchall()
    return [_to_post(row) for row in rows]


def list_scheduled_posts(conn: sqlite3.Connection) -> list[Post]:
    rows = conn.execute(
        "SELECT * FROM posts WHERE status = 'scheduled' ORDER BY scheduled_for ASC",
    ).fetchall()
    return [_to_post(row) for row in rows]
