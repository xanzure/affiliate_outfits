import sys, json
sys.path.insert(0, '.')
from app.db.pg_connection import connect_postgres
from app.db._helpers import utc_now

conn = connect_postgres('')
result = json.dumps({"error": "killed by Railway OOM - reset manually"})
conn.execute(
    "UPDATE jobs SET status=?, result_json=?, updated_at=? WHERE id=?",
    ("failed", result, utc_now(), "job_c1b7398d37894f04b2314bd8"),
)
row = conn.execute(
    "SELECT status FROM jobs WHERE id=?",
    ("job_c1b7398d37894f04b2314bd8",)
).fetchone()
print("status now:", row["status"])
conn.close()
