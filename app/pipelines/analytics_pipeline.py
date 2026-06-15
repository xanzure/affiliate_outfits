from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

from app.db.concepts import get_concept, update_concept_score
from app.db.metrics import record_metrics
from app.db.models import Concept, Metric
from app.db.posts import get_post
from app.services.analytics_service import (
    CombinedMetrics,
    combine_metrics,
    platform_metric_score,
    validate_performance_band,
)


@dataclass(frozen=True)
class ConceptMetricsResult:
    concept: Concept
    previous_score: float
    combined_metrics: CombinedMetrics
    recorded_metrics: list[Metric]


def apply_manual_metrics(conn: sqlite3.Connection, payload: dict[str, Any]) -> ConceptMetricsResult:
    concept_id = _require_string(payload, "concept_id")
    collection_window = payload.get("collection_window", "manual")
    collected_at = payload.get("collected_at")
    metric_entries = payload.get("metrics")
    if not isinstance(metric_entries, list) or not metric_entries:
        raise ValueError("metrics payload must include a non-empty 'metrics' list")

    concept = get_concept(conn, concept_id)
    recorded_metrics: list[Metric] = []

    for entry in metric_entries:
        if not isinstance(entry, dict):
            raise ValueError("each metrics entry must be an object")

        post_id = _require_string(entry, "post_id")
        post = get_post(conn, post_id)
        if post.concept_id != concept_id:
            raise ValueError(f"post {post_id} does not belong to concept {concept_id}")

        values = {
            "views": _read_int(entry, "views"),
            "likes": _read_int(entry, "likes"),
            "comments": _read_int(entry, "comments"),
            "shares": _read_int(entry, "shares"),
            "saves": _read_int(entry, "saves"),
            "clicks": _read_int(entry, "clicks"),
        }
        score = platform_metric_score(**values)
        recorded_metrics.append(
            record_metrics(
                conn,
                post_id=post_id,
                platform=post.platform,
                score=score,
                collected_at=entry.get("collected_at", collected_at),
                metadata={
                    "concept_id": concept_id,
                    "collection_window": collection_window,
                    "notes": entry.get("notes"),
                },
                **values,
            )
        )

    band_override = validate_performance_band(payload.get("performance_band"))
    combined = combine_metrics(recorded_metrics, performance_band_override=band_override)
    previous_score = concept.ranking_score
    concept = update_concept_score(conn, concept_id, previous_score + combined.score_adjustment)

    return ConceptMetricsResult(
        concept=concept,
        previous_score=previous_score,
        combined_metrics=combined,
        recorded_metrics=recorded_metrics,
    )


def _require_string(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"metrics payload field '{field}' must be a non-empty string")
    return value.strip()


def _read_int(payload: dict[str, Any], field: str) -> int:
    value = payload.get(field, 0)
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"metrics field '{field}' must be a non-negative integer")
    return value
