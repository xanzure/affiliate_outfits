from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.db.models import Metric


PerformanceBand = Literal["great", "good", "average", "weak", "bad"]


BAND_ADJUSTMENTS: dict[PerformanceBand, float] = {
    "great": 10,
    "good": 5,
    "average": 0,
    "weak": -5,
    "bad": -10,
}


@dataclass(frozen=True)
class CombinedMetrics:
    views: int
    likes: int
    comments: int
    shares: int
    saves: int
    clicks: int
    weighted_actions: float
    weighted_engagement_rate: float
    performance_band: PerformanceBand
    score_adjustment: float


def platform_metric_score(
    *,
    views: int,
    likes: int,
    comments: int,
    shares: int,
    saves: int,
    clicks: int,
) -> float:
    return (
        views * 0.01
        + likes
        + comments * 3
        + shares * 4
        + saves * 5
        + clicks * 8
    )


def combine_metrics(
    metrics: list[Metric],
    *,
    performance_band_override: PerformanceBand | None = None,
) -> CombinedMetrics:
    if not metrics:
        raise ValueError("at least one metric record is required")

    views = sum(metric.views for metric in metrics)
    likes = sum(metric.likes for metric in metrics)
    comments = sum(metric.comments for metric in metrics)
    shares = sum(metric.shares for metric in metrics)
    saves = sum(metric.saves for metric in metrics)
    clicks = sum(metric.clicks for metric in metrics)
    weighted_actions = likes + comments * 3 + shares * 4 + saves * 5 + clicks * 8
    weighted_engagement_rate = (weighted_actions / views * 100) if views > 0 else 0
    performance_band = performance_band_override or band_from_weighted_rate(weighted_engagement_rate)
    score_adjustment = BAND_ADJUSTMENTS[performance_band]

    return CombinedMetrics(
        views=views,
        likes=likes,
        comments=comments,
        shares=shares,
        saves=saves,
        clicks=clicks,
        weighted_actions=weighted_actions,
        weighted_engagement_rate=weighted_engagement_rate,
        performance_band=performance_band,
        score_adjustment=score_adjustment,
    )


def band_from_weighted_rate(weighted_engagement_rate: float) -> PerformanceBand:
    if weighted_engagement_rate >= 12:
        return "great"
    if weighted_engagement_rate >= 6:
        return "good"
    if weighted_engagement_rate >= 2:
        return "average"
    if weighted_engagement_rate >= 0.75:
        return "weak"
    return "bad"


def validate_performance_band(value: str | None) -> PerformanceBand | None:
    if value is None:
        return None
    if value not in BAND_ADJUSTMENTS:
        raise ValueError(f"invalid performance band: {value}")
    return value  # type: ignore[return-value]
