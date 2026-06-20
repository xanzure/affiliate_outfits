import sys
sys.path.insert(0, '.')
from app.db.pg_connection import connect_postgres

conn = connect_postgres('')
conn.execute("DELETE FROM admin_actions WHERE id IS NOT NULL")
conn.execute("DELETE FROM jobs WHERE id IS NOT NULL")
jobs = conn.execute("SELECT COUNT(*) as n FROM jobs").fetchone()
actions = conn.execute("SELECT COUNT(*) as n FROM admin_actions").fetchone()
print(f"jobs remaining: {jobs['n']}, admin_actions remaining: {actions['n']}")
conn.close()
