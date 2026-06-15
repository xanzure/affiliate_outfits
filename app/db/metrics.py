from __future__ import annotations

import sqlite3

from app.db._helpers import dumps_json, loads_json, new_id, require_row, utc_now
from app.db.models import JsonDict, Metric, Platform


def _to_metric(row: sqlite3.Row) -> Metric:
    return Metric(
        id=row["id"],
        post_id=row["post_id"],
        platform=row["platform"],
        collected_at=row["collected_at"],
        views=row["views"],
        likes=row["likes"],
        comments=row["comments"],
        shares=row["shares"],
        saves=row["saves"],
        clicks=row["clicks"],
        score=row["score"],
        metadata=loads_json(row["metadata_json"], {}),
    )


def record_metrics(
    conn: sqlite3.Connection,
    *,
    post_id: str,
    platform: Platform,
    views: int = 0,
    likes: int = 0,
    comments: int = 0,
    shares: int = 0,
    saves: int = 0,
    clicks: int = 0,
    score: float = 0,
    metadata: JsonDict | None = None,
    metric_id: str | None = None,
    collected_at: str | None = None,
) -> Metric:
    metric_id = metric_id or new_id("metric")
    conn.execute(
        """
        INSERT INTO metrics (
            id, post_id, platform, collected_at, views, likes, comments,
            shares, saves, clicks, score, metadata_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            metric_id,
            post_id,
            platform,
            collected_at or utc_now(),
            views,
            likes,
            comments,
            shares,
            saves,
            clicks,
            score,
            dumps_json(metadata or {}),
        ),
    )
    return get_metric(conn, metric_id)


def get_metric(conn: sqlite3.Connection, metric_id: str) -> Metric:
    row = conn.execute("SELECT * FROM metrics WHERE id = ?", (metric_id,)).fetchone()
    return _to_metric(require_row(row, "metric", metric_id))


def list_metrics_for_post(conn: sqlite3.Connection, post_id: str) -> list[Metric]:
    rows = conn.execute(
        "SELECT * FROM metrics WHERE post_id = ? ORDER BY collected_at DESC",
        (post_id,),
    ).fetchall()
    return [_to_metric(row) for row in rows]


def latest_metrics_for_post(conn: sqlite3.Connection, post_id: str) -> Metric | None:
    row = conn.execute(
        """
        SELECT * FROM metrics
        WHERE post_id = ?
        ORDER BY collected_at DESC
        LIMIT 1
        """,
        (post_id,),
    ).fetchone()
    return _to_metric(row) if row else None
