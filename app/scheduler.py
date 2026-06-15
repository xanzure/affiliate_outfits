from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

from app.creative_briefs import brief_from_concept_metadata, validate_brief
from app.db._helpers import est_days_ago, est_today, est_yesterday
from app.db.concepts import get_concept_by_seed, list_active_concepts, mark_concept_posted
from app.db.models import Concept


@dataclass(frozen=True)
class ScheduledConcept:
    concept_id: str
    seed: str
    brief: dict[str, Any]
    usage_count: int
    ranking_score: float
    last_posted_date_est: str | None


ScheduledBrief = ScheduledConcept


def select_daily_concepts(
    conn: sqlite3.Connection,
    *,
    count: int = 3,
    today_est: str | None = None,
    yesterday_est: str | None = None,
    day_before_yesterday_est: str | None = None,
) -> list[ScheduledConcept]:
    if count < 1:
        raise ValueError("count must be at least 1")

    today_est = today_est or est_today()
    yesterday_est = yesterday_est or est_yesterday()
    day_before_yesterday_est = day_before_yesterday_est or est_days_ago(2)
    excluded_dates = {today_est, yesterday_est, day_before_yesterday_est}
    concepts = [
        concept
        for concept in list_active_concepts(conn)
        if concept.last_posted_date_est not in excluded_dates
    ]
    return [_scheduled_concept_from_concept(concept) for concept in concepts[:count]]


def select_daily_concept(
    conn: sqlite3.Connection,
    *,
    today_est: str | None = None,
    yesterday_est: str | None = None,
    day_before_yesterday_est: str | None = None,
) -> ScheduledConcept | None:
    selected = select_daily_concepts(
        conn,
        count=1,
        today_est=today_est,
        yesterday_est=yesterday_est,
        day_before_yesterday_est=day_before_yesterday_est,
    )
    return selected[0] if selected else None


def mark_scheduled_concept_posted(
    conn: sqlite3.Connection,
    scheduled_concept: ScheduledConcept,
    *,
    posted_date_est: str | None = None,
) -> ScheduledConcept:
    concept = mark_concept_posted(
        conn,
        scheduled_concept.concept_id,
        posted_date_est=posted_date_est or est_today(),
    )
    return _scheduled_concept_from_concept(concept)


def select_concept_by_seed(conn: sqlite3.Connection, seed: str) -> ScheduledConcept:
    concept = get_concept_by_seed(conn, seed)
    if concept is None:
        raise LookupError(f"active concept not found for seed: {seed}")
    if concept.status != "active":
        raise ValueError(f"creative brief is not active: {seed}")
    return _scheduled_concept_from_concept(concept)


def _scheduled_concept_from_concept(concept: Concept) -> ScheduledConcept:
    brief = brief_from_concept_metadata(concept.seed, concept.metadata)
    validate_brief(brief)
    return ScheduledConcept(
        concept_id=concept.id,
        seed=brief["seed"],
        brief=brief,
        usage_count=concept.usage_count,
        ranking_score=concept.ranking_score,
        last_posted_date_est=concept.last_posted_date_est,
    )
