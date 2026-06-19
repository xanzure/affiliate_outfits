from __future__ import annotations

import sqlite3

from app.db._helpers import dumps_json, loads_json, new_id, utc_now


def create_job(conn: sqlite3.Connection, *, job_type: str, payload: dict) -> str:
    job_id = new_id("job")
    now = utc_now()
    conn.execute(
        """
        INSERT INTO jobs (id, type, payload_json, status, result_json, created_at, updated_at)
        VALUES (?, ?, ?, 'queued', '{}', ?, ?)
        """,
        (job_id, job_type, dumps_json(payload), now, now),
    )
    return job_id


def claim_next_job(conn: sqlite3.Connection) -> dict | None:
    """Return and mark the oldest queued job as running, or None."""
    row = conn.execute(
        "SELECT * FROM jobs WHERE status = 'queued' ORDER BY created_at ASC",
    ).fetchone()
    if not row:
        return None
    conn.execute(
        "UPDATE jobs SET status = 'running', updated_at = ? WHERE id = ?",
        (utc_now(), row["id"]),
    )
    return {
        "id": row["id"],
        "type": row["type"],
        "payload": loads_json(row["payload_json"], {}),
    }


def finish_job(conn: sqlite3.Connection, job_id: str, *, ok: bool, result: dict) -> None:
    conn.execute(
        "UPDATE jobs SET status = ?, result_json = ?, updated_at = ? WHERE id = ?",
        ("done" if ok else "failed", dumps_json(result), utc_now(), job_id),
    )
