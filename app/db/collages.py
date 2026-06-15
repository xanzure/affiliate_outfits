from __future__ import annotations

import sqlite3

from app.db._helpers import dumps_json, loads_json, new_id, require_row, utc_now
from app.db.models import Collage, JsonDict


def _to_collage(row: sqlite3.Row) -> Collage:
    return Collage(
        id=row["id"],
        outfit_id=row["outfit_id"],
        image_path=row["image_path"],
        collage_url=row["collage_url"],
        layout=loads_json(row["layout_json"], {}),
        created_at=row["created_at"],
        metadata=loads_json(row["metadata_json"], {}),
    )


def create_collage(
    conn: sqlite3.Connection,
    *,
    outfit_id: str,
    image_path: str,
    layout: JsonDict,
    collage_url: str | None = None,
    metadata: JsonDict | None = None,
    collage_id: str | None = None,
) -> Collage:
    collage_id = collage_id or new_id("collage")
    conn.execute(
        """
        INSERT INTO collages (
            id, outfit_id, image_path, collage_url, layout_json, created_at, metadata_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            collage_id,
            outfit_id,
            image_path,
            collage_url,
            dumps_json(layout),
            utc_now(),
            dumps_json(metadata or {}),
        ),
    )
    return get_collage(conn, collage_id)


def get_collage(conn: sqlite3.Connection, collage_id: str) -> Collage:
    row = conn.execute("SELECT * FROM collages WHERE id = ?", (collage_id,)).fetchone()
    return _to_collage(require_row(row, "collage", collage_id))


def list_collages_for_outfit(conn: sqlite3.Connection, outfit_id: str) -> list[Collage]:
    rows = conn.execute(
        "SELECT * FROM collages WHERE outfit_id = ? ORDER BY created_at DESC",
        (outfit_id,),
    ).fetchall()
    return [_to_collage(row) for row in rows]
