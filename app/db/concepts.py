from __future__ import annotations

import sqlite3

from app.db._helpers import dumps_json, loads_json, new_id, require_row, utc_now
from app.db.models import Concept, ConceptStatus, JsonDict


def _to_concept(row: sqlite3.Row) -> Concept:
    return Concept(
        id=row["id"],
        seed=row["seed"],
        status=row["status"],
        source=row["source"],
        usage_count=row["usage_count"],
        ranking_score=row["ranking_score"],
        last_posted_date_est=row["last_posted_date_est"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        metadata=loads_json(row["metadata_json"], {}),
    )


def create_concept(
    conn: sqlite3.Connection,
    seed: str,
    *,
    source: str = "seed",
    status: ConceptStatus = "active",
    ranking_score: float = 50,
    metadata: JsonDict | None = None,
    concept_id: str | None = None,
) -> Concept:
    now = utc_now()
    concept_id = concept_id or new_id("concept")
    conn.execute(
        """
        INSERT INTO concepts (
            id, seed, status, source, usage_count, ranking_score,
            last_posted_date_est, created_at, updated_at, metadata_json
        )
        VALUES (?, ?, ?, ?, 0, ?, NULL, ?, ?, ?)
        """,
        (concept_id, seed, status, source, ranking_score, now, now, dumps_json(metadata or {})),
    )
    return get_concept(conn, concept_id)


def upsert_concept(
    conn: sqlite3.Connection,
    seed: str,
    *,
    source: str = "seed",
    status: ConceptStatus = "active",
    ranking_score: float = 50,
    metadata: JsonDict | None = None,
    concept_id: str | None = None,
) -> Concept:
    existing = get_concept_by_seed(conn, seed)
    if existing is None:
        return create_concept(
            conn,
            seed,
            source=source,
            status=status,
            ranking_score=ranking_score,
            metadata=metadata,
            concept_id=concept_id,
        )

    now = utc_now()
    conn.execute(
        """
        UPDATE concepts
        SET source = ?,
            updated_at = ?,
            metadata_json = ?
        WHERE id = ?
        """,
        (source, now, dumps_json(metadata or {}), existing.id),
    )
    return get_concept(conn, existing.id)


def get_concept(conn: sqlite3.Connection, concept_id: str) -> Concept:
    row = conn.execute("SELECT * FROM concepts WHERE id = ?", (concept_id,)).fetchone()
    return _to_concept(require_row(row, "concept", concept_id))


def get_concept_by_seed(conn: sqlite3.Connection, seed: str) -> Concept | None:
    row = conn.execute("SELECT * FROM concepts WHERE seed = ?", (seed,)).fetchone()
    return _to_concept(row) if row else None


def update_concept_metadata(
    conn: sqlite3.Connection,
    concept_id: str,
    metadata: JsonDict,
) -> Concept:
    now = utc_now()
    conn.execute(
        """
        UPDATE concepts
        SET metadata_json = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (dumps_json(metadata), now, concept_id),
    )
    return get_concept(conn, concept_id)


def list_active_concepts(conn: sqlite3.Connection) -> list[Concept]:
    rows = conn.execute(
        """
        SELECT *
        FROM concepts
        WHERE status = 'active'
        ORDER BY ranking_score DESC, created_at ASC, seed ASC
        """
    ).fetchall()
    return [_to_concept(row) for row in rows]


def retire_active_concepts_not_in_seeds(conn: sqlite3.Connection, seeds: set[str]) -> int:
    now = utc_now()
    placeholders = ",".join("?" for _ in seeds)
    if not placeholders:
        result = conn.execute(
            """
            UPDATE concepts
            SET status = 'retired',
                updated_at = ?
            WHERE status = 'active'
            """,
            (now,),
        )
        return result.rowcount

    result = conn.execute(
        f"""
        UPDATE concepts
        SET status = 'retired',
            updated_at = ?
        WHERE status = 'active'
          AND seed NOT IN ({placeholders})
        """,
        (now, *sorted(seeds)),
    )
    return result.rowcount


def list_eligible_concepts(
    conn: sqlite3.Connection,
    *,
    excluded_posted_date_est: str | None,
    limit: int,
) -> list[Concept]:
    if excluded_posted_date_est:
        rows = conn.execute(
            """
            SELECT *
            FROM concepts
            WHERE status = 'active'
              AND (last_posted_date_est IS NULL OR last_posted_date_est != ?)
            ORDER BY ranking_score DESC, created_at ASC, seed ASC
            LIMIT ?
            """,
            (excluded_posted_date_est, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT *
            FROM concepts
            WHERE status = 'active'
            ORDER BY ranking_score DESC, created_at ASC, seed ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [_to_concept(row) for row in rows]


def mark_concept_posted(
    conn: sqlite3.Connection,
    concept_id: str,
    *,
    posted_date_est: str,
) -> Concept:
    now = utc_now()
    conn.execute(
        """
        UPDATE concepts
        SET usage_count = usage_count + 1,
            last_posted_date_est = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (posted_date_est, now, concept_id),
    )
    return get_concept(conn, concept_id)


def update_concept_score(conn: sqlite3.Connection, concept_id: str, ranking_score: float) -> Concept:
    clamped_score = min(100, max(0, ranking_score))
    status: ConceptStatus = "retired" if clamped_score < 25 else "active"
    now = utc_now()
    conn.execute(
        """
        UPDATE concepts
        SET ranking_score = ?,
            status = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (clamped_score, status, now, concept_id),
    )
    return get_concept(conn, concept_id)


def retire_concept(conn: sqlite3.Connection, concept_id: str) -> Concept:
    now = utc_now()
    conn.execute(
        "UPDATE concepts SET status = 'retired', updated_at = ? WHERE id = ?",
        (now, concept_id),
    )
    return get_concept(conn, concept_id)
