#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.pg_connection import connect_postgres
conn = connect_postgres("")
rows = conn.execute("SELECT id, type, status, payload_json, result_json, created_at FROM jobs ORDER BY created_at DESC LIMIT 20").fetchall()
print(f"Found {len(rows)} jobs:")
for r in rows:
    pid = r["payload_json"][:80] if r.get("payload_json") else ""
    rid = r["result_json"][:80] if r.get("result_json") else ""
    print(f"  [{r['status']:8}] {r['type']:20} {r['id'][:20]}  payload={pid}  result={rid}")
conn.close()
