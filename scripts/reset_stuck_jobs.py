#!/usr/bin/env python3
"""Reset jobs stuck in 'running' back to 'queued' so the worker can retry them."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.pg_connection import connect_postgres
from app.db._helpers import utc_now

conn = connect_postgres("")
rows = conn.execute("SELECT id, type, payload_json FROM jobs WHERE status = 'running'").fetchall()
print(f"Found {len(rows)} stuck jobs:")
for r in rows:
    print(f"  {r['id']} ({r['type']}) payload={r['payload_json'][:80]}")
    conn.execute(
        "UPDATE jobs SET status = 'queued', updated_at = ? WHERE id = ?",
        (utc_now(), r["id"]),
    )
    print(f"  → reset to queued")
conn.close()
print("done")
