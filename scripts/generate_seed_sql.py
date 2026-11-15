"""Print SQL that seeds the concept pool into Supabase.

Paste the output into the Supabase SQL editor after running
app/db/schema_postgres.sql. Concepts are stored with the full normalized creative
brief — the same shape scripts/seed_concepts.py writes locally — so the outfit
agent receives the brief's context, not just the seed phrase.

    python scripts/generate_seed_sql.py > seed.sql
"""
from __future__ import annotations

import datetime
import json
import uuid

try:
    from _bootstrap import add_project_root_to_path
except ModuleNotFoundError:
    from scripts._bootstrap import add_project_root_to_path

add_project_root_to_path()

from app.config import PROJECT_ROOT
from app.creative_briefs import normalize_brief


def _sql_text(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def main() -> None:
    concepts = json.loads((PROJECT_ROOT / "data/concepts/seed_concepts.json").read_text(encoding="utf-8"))
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = []
    for concept in concepts:
        brief = normalize_brief(concept)
        metadata = {**concept.get("metadata", {}), "brief_schema_version": 1, "brief": brief.payload}
        rows.append(
            "("
            + ", ".join(
                [
                    _sql_text("concept_" + uuid.uuid4().hex[:16]),
                    _sql_text(brief.seed),
                    _sql_text(concept.get("status", "active")),
                    "'seed'",
                    "0",
                    str(float(concept.get("ranking_score", 50))),
                    "NULL",
                    _sql_text(now),
                    _sql_text(now),
                    _sql_text(json.dumps(metadata)),
                ]
            )
            + ")"
        )

    print(
        "INSERT INTO concepts (id, seed, status, source, usage_count, ranking_score, "
        "last_posted_date_est, created_at, updated_at, metadata_json) VALUES"
    )
    print(",\n".join(rows) + ";")


if __name__ == "__main__":
    main()
