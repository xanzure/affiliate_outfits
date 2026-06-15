import json
import uuid
import datetime

with open("data/concepts/seed_concepts.json") as f:
    concepts = json.load(f)

now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
rows = []
for c in concepts:
    cid = "concept_" + uuid.uuid4().hex[:16]
    metadata = json.dumps(c.get("metadata", {})).replace("'", "''")
    seed = c["seed"].replace("'", "''")
    rows.append(
        f"('{cid}', '{seed}', 'active', 'seed', 0, 50, NULL, '{now}', '{now}', '{metadata}')"
    )

print("INSERT INTO concepts (id, seed, status, source, usage_count, ranking_score, last_posted_date_est, created_at, updated_at, metadata_json) VALUES")
print(",\n".join(rows) + ";")
