from __future__ import annotations

from app.db.models import Concept


def concept_summary(concept: Concept) -> dict[str, object]:
    brief = concept.metadata.get("brief")
    return {
        "id": concept.id,
        "seed": concept.seed,
        "status": concept.status,
        "ranking_score": concept.ranking_score,
        "usage_count": concept.usage_count,
        "last_posted_date_est": concept.last_posted_date_est,
        "brief": brief if isinstance(brief, dict) else {},
    }


def replacement_history_payload(
    *,
    retired_concept: Concept,
    active_concepts: list[Concept],
) -> dict[str, object]:
    return {
        "retired_concept": concept_summary(retired_concept),
        "active_concepts": [concept_summary(concept) for concept in active_concepts],
    }
