import unittest

from app.db.models import Metric
from app.services.analytics_service import (
    band_from_weighted_rate,
    combine_metrics,
    platform_metric_score,
)


class AnalyticsServiceTests(unittest.TestCase):
    def test_platform_metric_score_weights_actions(self) -> None:
        score = platform_metric_score(
            views=100,
            likes=1,
            comments=1,
            shares=1,
            saves=1,
            clicks=1,
        )

        self.assertEqual(score, 22)

    def test_band_from_weighted_rate(self) -> None:
        self.assertEqual(band_from_weighted_rate(12), "great")
        self.assertEqual(band_from_weighted_rate(6), "good")
        self.assertEqual(band_from_weighted_rate(2), "average")
        self.assertEqual(band_from_weighted_rate(0.75), "weak")
        self.assertEqual(band_from_weighted_rate(0.1), "bad")

    def test_combine_metrics_uses_mirrored_platform_totals(self) -> None:
        metrics = [
            Metric(
                id="m1",
                post_id="p1",
                platform="tiktok",
                collected_at="2026-06-14T00:00:00+00:00",
                views=1000,
                likes=40,
                comments=5,
                shares=5,
                saves=10,
                clicks=5,
                score=0,
            ),
            Metric(
                id="m2",
                post_id="p2",
                platform="pinterest",
                collected_at="2026-06-14T00:00:00+00:00",
                views=1000,
                likes=20,
                comments=0,
                shares=5,
                saves=20,
                clicks=10,
                score=0,
            ),
        ]

        combined = combine_metrics(metrics)

        self.assertEqual(combined.views, 2000)
        self.assertEqual(combined.clicks, 15)
        self.assertEqual(combined.performance_band, "great")
        self.assertEqual(combined.score_adjustment, 10)


if __name__ == "__main__":
    unittest.main()
