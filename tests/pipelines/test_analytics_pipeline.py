import tempfile
import unittest
from pathlib import Path

from app.db.concepts import create_concept, get_concept
from app.db.outfits import create_outfit
from app.db.posts import create_post
from app.pipelines.analytics_pipeline import apply_manual_metrics
from app.services.storage_service import connect, initialize_database


class AnalyticsPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "analytics.sqlite3"
        initialize_database(self.database_path)
        self.conn = connect(self.database_path)

    def tearDown(self) -> None:
        self.conn.close()
        self.temp_dir.cleanup()

    def _create_mirrored_posts(
        self,
        *,
        ranking_score: float = 50,
        seed: str = "Bad Bunny summer concert outfit",
    ):
        concept = create_concept(
            self.conn,
            seed,
            ranking_score=ranking_score,
            metadata={"brief": {"seed": seed}},
        )
        outfit = create_outfit(
            self.conn,
            concept_id=concept.id,
            concept_seed=concept.seed,
            spec={"outfit": {"title": "Summer Concert Streetwear"}},
        )
        tiktok = create_post(
            self.conn,
            platform="tiktok",
            concept_id=concept.id,
            outfit_id=outfit.id,
        )
        pinterest = create_post(
            self.conn,
            platform="pinterest",
            concept_id=concept.id,
            outfit_id=outfit.id,
        )
        self.conn.commit()
        return concept, tiktok, pinterest

    def test_apply_manual_metrics_updates_concept_score(self) -> None:
        concept, tiktok, pinterest = self._create_mirrored_posts()

        result = apply_manual_metrics(
            self.conn,
            {
                "concept_id": concept.id,
                "collection_window": "manual",
                "metrics": [
                    {
                        "post_id": tiktok.id,
                        "views": 1000,
                        "likes": 80,
                        "comments": 8,
                        "shares": 8,
                        "saves": 12,
                        "clicks": 10,
                    },
                    {
                        "post_id": pinterest.id,
                        "views": 1000,
                        "likes": 30,
                        "comments": 2,
                        "shares": 5,
                        "saves": 20,
                        "clicks": 10,
                    },
                ],
            },
        )
        self.conn.commit()

        self.assertEqual(len(result.recorded_metrics), 2)
        self.assertEqual(result.previous_score, 50)
        self.assertEqual(result.concept.ranking_score, 60)
        self.assertEqual(get_concept(self.conn, concept.id).ranking_score, 60)

    def test_apply_manual_metrics_retires_concept_below_threshold(self) -> None:
        concept, tiktok, pinterest = self._create_mirrored_posts(ranking_score=30)

        result = apply_manual_metrics(
            self.conn,
            {
                "concept_id": concept.id,
                "performance_band": "bad",
                "metrics": [
                    {"post_id": tiktok.id, "views": 1000},
                    {"post_id": pinterest.id, "views": 1000},
                ],
            },
        )
        self.conn.commit()

        self.assertEqual(result.concept.ranking_score, 20)
        self.assertEqual(result.concept.status, "retired")

    def test_apply_manual_metrics_rejects_wrong_concept_post(self) -> None:
        concept, tiktok, _ = self._create_mirrored_posts()
        other_concept, _, _ = self._create_mirrored_posts(
            ranking_score=70,
            seed="Dark academia rainy campus outfit",
        )

        with self.assertRaises(ValueError):
            apply_manual_metrics(
                self.conn,
                {
                    "concept_id": other_concept.id,
                    "metrics": [{"post_id": tiktok.id, "views": 1}],
                },
            )


if __name__ == "__main__":
    unittest.main()
