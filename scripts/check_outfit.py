#!/usr/bin/env python3
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.pg_connection import connect_postgres

conn = connect_postgres("")

# Find Morgan Wallen concept
concepts = conn.execute("SELECT id, seed, status FROM concepts WHERE seed ILIKE '%morgan%' OR seed ILIKE '%wallen%'").fetchall()
print("Concepts:", concepts)

for c in concepts:
    outfits = conn.execute("SELECT id, created_at FROM outfits WHERE concept_id = ?", (c["id"],)).fetchall()
    print(f"\nOutfits for {c['seed']} ({len(outfits)}):")
    for o in outfits:
        posts = conn.execute("SELECT id, platform, status, approved FROM posts WHERE outfit_id = ?", (o["id"],)).fetchall()
        print(f"  outfit {o['id'][:24]} created={o['created_at'][:10]}")
        for p in posts:
            print(f"    post [{p['platform']}] status={p['status']} approved={p['approved']}")

conn.close()
