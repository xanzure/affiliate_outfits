from __future__ import annotations

import sqlite3

from app.db._helpers import dumps_json, loads_json, new_id, require_row, utc_now
from app.db.models import JsonDict, Outfit


def _to_outfit(row: sqlite3.Row) -> Outfit:
    return Outfit(
        id=row["id"],
        concept_id=row["concept_id"],
        concept_seed=row["concept_seed"],
        spec=loads_json(row["spec_json"], {}),
        product_ids=loads_json(row["product_ids_json"], []),
        created_at=row["created_at"],
        metadata=loads_json(row["metadata_json"], {}),
    )


def create_outfit(
    conn: sqlite3.Connection,
    *,
    concept_seed: str,
    spec: JsonDict,
    concept_id: str | None = None,
    product_ids: list[str] | None = None,
    metadata: JsonDict | None = None,
    outfit_id: str | None = None,
) -> Outfit:
    outfit_id = outfit_id or new_id("outfit")
    conn.execute(
        """
        INSERT INTO outfits (
            id, concept_id, concept_seed, spec_json, product_ids_json,
            created_at, metadata_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            outfit_id,
            concept_id,
            concept_seed,
            dumps_json(spec),
            dumps_json(product_ids or []),
            utc_now(),
            dumps_json(metadata or {}),
        ),
    )
    return get_outfit(conn, outfit_id)


def get_outfit(conn: sqlite3.Connection, outfit_id: str) -> Outfit:
    row = conn.execute("SELECT * FROM outfits WHERE id = ?", (outfit_id,)).fetchone()
    return _to_outfit(require_row(row, "outfit", outfit_id))


def update_outfit_spec(conn: sqlite3.Connection, outfit_id: str, spec: JsonDict) -> Outfit:
    conn.execute(
        "UPDATE outfits SET spec_json = ? WHERE id = ?",
        (dumps_json(spec), outfit_id),
    )
    return get_outfit(conn, outfit_id)


def list_outfits_for_concept(conn: sqlite3.Connection, concept_id: str) -> list[Outfit]:
    rows = conn.execute(
        "SELECT * FROM outfits WHERE concept_id = ? ORDER BY created_at DESC",
        (concept_id,),
    ).fetchall()
    return [_to_outfit(row) for row in rows]
