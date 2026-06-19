#!/usr/bin/env python3
"""Seed a few demo posts (varied states) for existing outfits so the admin
dashboard Schedule tab has content to render. Safe to re-run (clears demo posts)."""
from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.pg_connection import connect_postgres
from app.db.posts import create_post


def main() -> None:
    conn = connect_postgres("")
    # collage url per outfit
    outfits = conn.execute(
        "SELECT o.id, o.concept_id, c.collage_url FROM outfits o "
        "LEFT JOIN collages c ON c.outfit_id = o.id"
    ).fetchall()
    if not outfits:
        print("no outfits to seed")
        return

    conn.execute("DELETE FROM posts WHERE metadata_json LIKE '%\"demo\": true%'")

    now = datetime.now(UTC)
    o = outfits[0]
    oid, cid, curl = o["id"], o["concept_id"], o["collage_url"]
    base_meta = {"demo": True, "outfit_ids": [oid], "title": "Bad Bunny Concert"}

    # TikTok slideshow — needs approval
    create_post(
        conn, platform="tiktok", concept_id=cid, outfit_id=oid,
        image_path=curl, caption="San Juan nights energy ☀️🔥 #badbunny #concertfit #ootd",
        status="draft", approved=False,
        metadata={**base_meta, "slide_urls": [curl, curl, curl]},
    )
    # Pinterest — queued (approved, unscheduled)
    create_post(
        conn, platform="pinterest", concept_id=cid, outfit_id=oid,
        image_path=curl, caption="Tropical reggaeton glam — shop the look.",
        status="draft", approved=True, queue_order=now.isoformat(),
        metadata={**base_meta, "slide_urls": [curl], "title": "San Juan Nights"},
    )
    # Pinterest — already scheduled
    create_post(
        conn, platform="pinterest", concept_id=cid, outfit_id=oid,
        image_path=curl, caption="Statement gold + cobalt for the show.",
        status="scheduled", approved=True, is_manual_schedule=False,
        scheduled_for=(now + timedelta(hours=4)).isoformat(),
        metadata={**base_meta, "slide_urls": [curl], "title": "Reggaeton Glam"},
    )
    print("seeded 3 demo posts for outfit", oid[:16])
    conn.close()


if __name__ == "__main__":
    main()
