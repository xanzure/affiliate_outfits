import tempfile
import unittest
from pathlib import Path

from app.db.concepts import create_concept, get_concept
from app.scheduler import (
    mark_scheduled_concept_posted,
    select_concept_by_seed,
    select_daily_concept,
    select_daily_concepts,
)
from app.services.storage_service import connect, initialize_database


class SchedulerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "scheduler.sqlite3"
        initialize_database(self.database_path)
        self.conn = connect(self.database_path)

    def tearDown(self) -> None:
        self.conn.close()
        self.temp_dir.cleanup()

    def test_select_daily_concepts_returns_active_concept_payloads(self) -> None:
        concept = create_concept(
            self.conn,
            "Bad Bunny summer concert outfit",
            metadata={
                "brief": {
                    "seed": "Bad Bunny summer concert outfit",
                    "context_notes": ["Puerto Rican cultural references are relevant"],
                    "style_cues": ["streetwear"],
                    "avoid": ["costume styling"],
                }
            },
        )
        self.conn.commit()

        scheduled = select_daily_concepts(self.conn, count=1, today_est="2026-06-14", yesterday_est="2026-06-13")

        self.assertEqual(scheduled[0].concept_id, concept.id)
        self.assertEqual(scheduled[0].seed, "Bad Bunny summer concert outfit")
        self.assertEqual(
            scheduled[0].brief["context_notes"],
            ["Puerto Rican cultural references are relevant"],
        )

    def test_mark_scheduled_concept_posted_increments_usage_count(self) -> None:
        concept = create_concept(
            self.conn,
            "city weekend outfit",
            metadata={"brief": {"seed": "city weekend outfit"}},
        )
        self.conn.commit()

        selected = select_daily_concepts(
            self.conn,
            count=1,
            today_est="2026-06-14",
            yesterday_est="2026-06-13",
        )
        reserved = [mark_scheduled_concept_posted(self.conn, selected[0], posted_date_est="2026-06-14")]
        self.conn.commit()

        self.assertEqual(reserved[0].usage_count, 1)
        self.assertEqual(get_concept(self.conn, concept.id).usage_count, 1)

    def test_scheduler_prefers_highest_ranking_concept(self) -> None:
        first = create_concept(
            self.conn,
            "first",
            ranking_score=40,
            metadata={"brief": {"seed": "first"}},
        )
        second = create_concept(
            self.conn,
            "second",
            ranking_score=80,
            metadata={"brief": {"seed": "second"}},
        )
        self.conn.commit()

        next_due = select_daily_concepts(
            self.conn,
            count=1,
            today_est="2026-06-14",
            yesterday_est="2026-06-13",
        )

        self.assertEqual(next_due[0].concept_id, second.id)
        self.assertNotEqual(next_due[0].concept_id, first.id)

    def test_select_concept_by_seed(self) -> None:
        concept = create_concept(
            self.conn,
            "specific seed",
            metadata={"brief": {"seed": "specific seed"}},
        )
        self.conn.commit()

        scheduled = mark_scheduled_concept_posted(
            self.conn,
            select_concept_by_seed(self.conn, "specific seed"),
            posted_date_est="2026-06-14",
        )
        self.conn.commit()

        self.assertEqual(scheduled.concept_id, concept.id)
        self.assertEqual(get_concept(self.conn, concept.id).usage_count, 1)

    def test_select_daily_concepts_excludes_today_yesterday_and_day_before_est(self) -> None:
        today = "2026-06-14"
        yesterday = "2026-06-13"
        day_before = "2026-06-12"
        older = create_concept(
            self.conn,
            "older",
            ranking_score=60,
            metadata={"brief": {"seed": "older"}},
        )
        today_concept = create_concept(
            self.conn,
            "today",
            ranking_score=100,
            metadata={"brief": {"seed": "today"}},
        )
        yesterday_concept = create_concept(
            self.conn,
            "yesterday",
            ranking_score=90,
            metadata={"brief": {"seed": "yesterday"}},
        )
        day_before_concept = create_concept(
            self.conn,
            "day before",
            ranking_score=80,
            metadata={"brief": {"seed": "day before"}},
        )
        self.conn.commit()
        mark_scheduled_concept_posted(
            self.conn,
            select_concept_by_seed(self.conn, "today"),
            posted_date_est=today,
        )
        mark_scheduled_concept_posted(
            self.conn,
            select_concept_by_seed(self.conn, "yesterday"),
            posted_date_est=yesterday,
        )
        mark_scheduled_concept_posted(
            self.conn,
            select_concept_by_seed(self.conn, "day before"),
            posted_date_est=day_before,
        )
        self.conn.commit()

        selected = select_daily_concepts(
            self.conn,
            count=3,
            today_est=today,
            yesterday_est=yesterday,
            day_before_yesterday_est=day_before,
        )

        self.assertEqual([item.concept_id for item in selected], [older.id])
        self.assertNotIn(today_concept.id, [item.concept_id for item in selected])
        self.assertNotIn(yesterday_concept.id, [item.concept_id for item in selected])
        self.assertNotIn(day_before_concept.id, [item.concept_id for item in selected])

    def test_select_daily_concept_returns_only_top_ranked_eligible_concept(self) -> None:
        create_concept(self.conn, "lower", ranking_score=40, metadata={"brief": {"seed": "lower"}})
        top = create_concept(self.conn, "top", ranking_score=90, metadata={"brief": {"seed": "top"}})
        self.conn.commit()

        selected = select_daily_concept(
            self.conn,
            today_est="2026-06-14",
            yesterday_est="2026-06-13",
            day_before_yesterday_est="2026-06-12",
        )

        self.assertIsNotNone(selected)
        self.assertEqual(selected.concept_id, top.id)


if __name__ == "__main__":
    unittest.main()
