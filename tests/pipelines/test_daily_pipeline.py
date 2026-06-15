import tempfile
import unittest
from pathlib import Path

from app.config import Settings
from app.db.collages import list_collages_for_outfit
from app.db.concepts import get_concept
from app.db.outfits import get_outfit
from app.db.concepts import create_concept
from app.pipelines.daily_pipeline import run_daily_for_brief, run_daily_outfit_set_for_concept
from app.scheduler import select_daily_concepts
from app.services.storage_service import connect, initialize_database


OUTFIT_OUTPUT = {
    "interpretation": {
        "primary_reference": "Bad Bunny",
        "used_cues": ["streetwear", "statement accessories"],
        "discarded_cues": [],
        "rationale": "Uses brief-specific styling cues.",
    },
    "outfit": {
        "title": "Summer Concert Streetwear",
        "categories": ["top", "bottom", "accessory"],
        "colors": ["red", "white", "blue"],
        "materials": ["nylon"],
        "accessories": ["statement sunglasses"],
    },
    "search_queries": [
        {"query": "red summer concert streetwear camp collar", "category": "top", "limit": 1},
        {"query": "blue relaxed cargo concert streetwear", "category": "bottom", "limit": 1},
        {"query": "white statement concert sunglasses", "category": "accessory", "limit": 1},
    ],
    "diversity_notes": ["Avoided generic summer outfit."],
}

ENGAGEMENT_OUTPUT = {
    "tiktok": {
        "caption": "Concert outfit with relaxed streetwear.",
        "hashtags": ["concertoutfit"],
        "music_category": "latin pop",
    },
    "pinterest": {
        "title": "Summer Concert Streetwear Outfit",
        "description": "A warm-weather concert outfit.",
        "hashtags": ["concert outfit"],
    },
    "notes": [],
}

BATCH_OUTFIT_OUTPUT = {
    "outfits": [
        {
            **OUTFIT_OUTPUT,
            "outfit": {
                **OUTFIT_OUTPUT["outfit"],
                "title": f"Summer Concert Streetwear {index}",
            },
        }
        for index in range(1, 6)
    ]
}

BATCH_ENGAGEMENT_OUTPUT = {
    "tiktok": {
        "caption": "Five concert outfits with relaxed streetwear.",
        "hashtags": ["concertoutfit"],
        "music_category": "latin pop",
    },
    "pinterest_posts": [
        {
            "title": f"Summer Concert Streetwear Outfit {index}",
            "description": f"A warm-weather concert outfit idea {index}.",
            "hashtags": ["concert outfit"],
        }
        for index in range(1, 6)
    ],
    "notes": [],
}


class DailyPipelineTests(unittest.TestCase):
    def test_run_daily_for_brief_creates_local_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            database_path = root / "daily.sqlite3"
            initialize_database(database_path)
            conn = connect(database_path)
            settings = Settings(
                app_env="test",
                log_level="WARNING",
                database_path=database_path,
                data_dir=root / "data",
                assets_dir=root / "assets",
                dry_run=True,
                ai_mode="claude",
            )
            try:
                create_concept(
                    conn,
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
                scheduled = select_daily_concepts(
                    conn,
                    count=1,
                    today_est="2026-06-14",
                    yesterday_est="2026-06-13",
                )[0]

                result = run_daily_for_brief(
                    conn,
                    scheduled,
                    outfit_output=OUTFIT_OUTPUT,
                    engagement_output=ENGAGEMENT_OUTPUT,
                    settings=settings,
                )
                conn.commit()

                stored_outfit = get_outfit(conn, result.outfit.id)
                self.assertEqual(stored_outfit.concept_seed, "Bad Bunny summer concert outfit")
                self.assertGreaterEqual(len(result.products), 3)
                self.assertEqual(len(result.prepared_images), len(result.products))
                self.assertTrue(result.collage_path.exists())
                self.assertIsNotNone(result.collage_id)
                stored_collage = list_collages_for_outfit(conn, result.outfit.id)[0]
                self.assertEqual(stored_collage.id, result.collage_id)
                self.assertEqual(stored_collage.layout["pieces"][0]["product_id"], result.products[0].id)
                self.assertEqual(stored_outfit.spec["layout"][0]["product_id"], result.products[0].id)
                self.assertIn("rotation", stored_outfit.spec["layout"][0])
                self.assertIn("z_index", stored_outfit.spec["layout"][0])
                self.assertEqual(stored_outfit.product_ids, [product.id for product in result.products])
                self.assertIsNotNone(result.publish_result)
                self.assertEqual(len(result.publish_result.posts), 2)
            finally:
                conn.close()

    def test_run_daily_for_brief_rejects_invalid_outfit_output_before_creating_outfit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            database_path = root / "daily.sqlite3"
            initialize_database(database_path)
            conn = connect(database_path)
            settings = Settings(
                app_env="test",
                log_level="WARNING",
                database_path=database_path,
                data_dir=root / "data",
                assets_dir=root / "assets",
                dry_run=True,
                ai_mode="claude",
            )
            try:
                create_concept(conn, "Bad Bunny concert", metadata={"brief": {"seed": "Bad Bunny concert"}})
                scheduled = select_daily_concepts(
                    conn,
                    count=1,
                    today_est="2026-06-14",
                    yesterday_est="2026-06-13",
                )[0]

                with self.assertRaisesRegex(ValueError, "interpretation"):
                    run_daily_for_brief(
                        conn,
                        scheduled,
                        outfit_output={"outfit": {"title": "Too small"}},
                        engagement_output=ENGAGEMENT_OUTPUT,
                        settings=settings,
                    )
            finally:
                conn.close()

    def test_run_daily_outfit_set_for_concept_creates_five_outfits_and_six_posts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            database_path = root / "daily.sqlite3"
            initialize_database(database_path)
            conn = connect(database_path)
            settings = Settings(
                app_env="test",
                log_level="WARNING",
                database_path=database_path,
                data_dir=root / "data",
                assets_dir=root / "assets",
                dry_run=True,
                ai_mode="claude",
            )
            try:
                create_concept(
                    conn,
                    "Bad Bunny concert",
                    metadata={"brief": {"seed": "Bad Bunny concert", "style_cues": ["streetwear"]}},
                )
                scheduled = select_daily_concepts(
                    conn,
                    count=1,
                    today_est="2026-06-14",
                    yesterday_est="2026-06-13",
                    day_before_yesterday_est="2026-06-12",
                )[0]

                result = run_daily_outfit_set_for_concept(
                    conn,
                    scheduled,
                    outfit_batch_output=BATCH_OUTFIT_OUTPUT,
                    engagement_output=BATCH_ENGAGEMENT_OUTPUT,
                    settings=settings,
                )
                conn.commit()

                self.assertEqual(len(result.outfit_results), 5)
                self.assertTrue(all(item.collage_path.exists() for item in result.outfit_results))
                self.assertTrue(all(item.collage_id for item in result.outfit_results))
                first_collage = list_collages_for_outfit(conn, result.outfit_results[0].outfit.id)[0]
                first_outfit = get_outfit(conn, result.outfit_results[0].outfit.id)
                self.assertEqual(
                    first_collage.layout["pieces"][0]["product_id"],
                    result.outfit_results[0].products[0].id,
                )
                self.assertEqual(
                    first_outfit.spec["layout"][0]["product_id"],
                    result.outfit_results[0].products[0].id,
                )
                self.assertLessEqual(first_outfit.spec["layout"][0]["x"], 100)
                self.assertLessEqual(first_outfit.spec["layout"][0]["width"], 100)
                concept = get_concept(conn, scheduled.concept_id)
                self.assertEqual(concept.metadata["cover_image_url"], str(result.outfit_results[0].collage_path))
                self.assertIsNotNone(result.publish_result)
                self.assertEqual(len(result.publish_result.posts), 6)
                self.assertEqual(
                    len([post for post in result.publish_result.posts if post.platform == "tiktok"]),
                    1,
                )
                self.assertEqual(
                    len([post for post in result.publish_result.posts if post.platform == "pinterest"]),
                    5,
                )
                self.assertEqual(result.scheduled_concept.usage_count, 1)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
