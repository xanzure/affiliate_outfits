import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from app.agents.engagement.agent import generate_engagement_with_llm
from app.agents.engagement.templates import build_engagement_prompt
from app.config import Settings
from app.db.outfits import create_outfit
from app.db.posts import list_posts
from app.db.products import upsert_product
from app.pipelines.publish_pipeline import (
    autopublish_posts,
    create_local_publish_records,
    create_local_publish_records_for_outfit_set,
)
from app.services.pinterest_service import PinterestPublishResult
from app.services.storage_service import connect, initialize_database
from app.services.tiktok_service import TikTokPublishResult

class FakeLLMService:
    def __init__(self, response: dict) -> None:
        self.response = response
        self.prompts = []

    def request_json(self, prompt):
        self.prompts.append(prompt)
        return self.response


class FakeTikTokClient:
    def __init__(self) -> None:
        self.requests = []

    def publish_photo_slideshow(self, *, image_urls, caption, title=None):
        self.requests.append({"image_urls": image_urls, "caption": caption, "title": title})
        return TikTokPublishResult(
            publish_id="tiktok_publish_123",
            raw_response={"data": {"publish_id": "tiktok_publish_123"}, "error": {"code": "ok"}},
        )


class FakePinterestClient:
    def __init__(self) -> None:
        self.requests = []

    def create_pin(self, *, image_url, title, description, link=None):
        self.requests.append(
            {"image_url": image_url, "title": title, "description": description, "link": link}
        )
        return PinterestPublishResult(pin_id="pin_123", raw_response={"id": "pin_123"})


ENGAGEMENT_OUTPUT = {
    "tiktok": {
        "caption": "Concert outfit with bold color and statement accessories.",
        "hashtags": ["concertoutfit", "affiliatefinds"],
        "music_category": "latin pop",
    },
    "pinterest": {
        "title": "Summer Concert Streetwear Outfit",
        "description": "A warm-weather concert outfit with relaxed streetwear pieces.",
        "hashtags": ["concert outfit", "summer outfit"],
    },
    "notes": ["Kept copy concise."],
}


class EngagementPublishTests(unittest.TestCase):
    def test_build_engagement_prompt_contains_brief_and_schema(self) -> None:
        prompt = build_engagement_prompt(
            {"seed": "Bad Bunny summer concert outfit"},
            {"title": "Summer Concert Streetwear"},
            [{"name": "White Retro Sport Sunglasses"}],
        )

        self.assertIn("Bad Bunny summer concert outfit", prompt)
        self.assertIn("White Retro Sport Sunglasses", prompt)
        self.assertIn('"tiktok"', prompt)
        self.assertIn('"pinterest"', prompt)

    def test_engagement_agent_uses_llm_service(self) -> None:
        service = FakeLLMService(
            {
                "tiktok": {"caption": "Test caption", "hashtags": ["test"], "music_category": "pop"},
                "pinterest": {
                    "title": "Test title",
                    "description": "Test description",
                    "hashtags": ["test"],
                },
                "notes": [],
            }
        )

        result = generate_engagement_with_llm(
            {"seed": "test"},
            {"title": "test outfit"},
            [],
            llm_service=service,
        )

        self.assertEqual(result["tiktok"]["caption"], "Test caption")
        self.assertIn("Engagement Agent", service.prompts[0].title)

    def test_create_local_publish_records_creates_drafts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "publish.sqlite3"
            initialize_database(database_path)
            conn = connect(database_path)
            try:
                outfit = create_outfit(
                    conn,
                    concept_seed="Bad Bunny summer concert outfit",
                    spec={"outfit": {"title": "Summer Concert Streetwear"}},
                )
                product = upsert_product(
                    conn,
                    retailer="Local Rack",
                    name="White Retro Sport Sunglasses",
                    category="accessory",
                    url="https://example.test/sunglasses",
                    affiliate_url="https://example.test/sunglasses?aff_id=test",
                )
                result = create_local_publish_records(
                    conn,
                    concept_id=None,
                    outfit=outfit,
                    products=[product],
                    collage_path=Path("data/images/collages/test.png"),
                    engagement_output=ENGAGEMENT_OUTPUT,
                )
                conn.commit()

                posts = list_posts(conn)
                self.assertEqual(len(result.posts), 2)
                self.assertEqual(len(posts), 2)
                self.assertEqual({post.platform for post in posts}, {"tiktok", "pinterest"})
                self.assertTrue(all(post.status == "draft" for post in posts))
                self.assertTrue(all(post.metadata["local_only"] for post in posts))
            finally:
                conn.close()

    def test_create_local_publish_records_for_outfit_set_creates_slideshow_and_scheduled_pins(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "publish.sqlite3"
            initialize_database(database_path)
            conn = connect(database_path)
            try:
                outfits = [
                    create_outfit(
                        conn,
                        concept_seed="Bad Bunny concert",
                        spec={"outfit": {"title": f"Look {index}"}},
                    )
                    for index in range(1, 6)
                ]
                product = upsert_product(
                    conn,
                    retailer="Local Rack",
                    name="White Retro Sport Sunglasses",
                    category="accessory",
                    url="https://example.test/sunglasses",
                    affiliate_url="https://example.test/sunglasses?aff_id=test",
                )
                engagement = {
                    "tiktok": {
                        "caption": "Five concert outfits.",
                        "hashtags": ["concertoutfit"],
                        "music_category": "latin pop",
                    },
                    "pinterest_posts": [
                        {
                            "title": f"Concert Outfit {index}",
                            "description": f"Look {index} for the concert.",
                            "hashtags": ["concert outfit"],
                        }
                        for index in range(1, 6)
                    ],
                    "notes": [],
                }

                result = create_local_publish_records_for_outfit_set(
                    conn,
                    outfits=outfits,
                    products_by_outfit=[[product] for _ in outfits],
                    collage_paths=[Path(f"data/images/collages/look-{index}.png") for index in range(1, 6)],
                    engagement_output=engagement,
                    schedule_date_est="2026-06-14",
                )
                conn.commit()

                self.assertEqual(len(result.posts), 6)
                tiktok_posts = [post for post in result.posts if post.platform == "tiktok"]
                pinterest_posts = [post for post in result.posts if post.platform == "pinterest"]
                self.assertEqual(len(tiktok_posts), 1)
                self.assertEqual(len(pinterest_posts), 5)
                self.assertEqual(tiktok_posts[0].metadata["post_format"], "slideshow")
                self.assertEqual(len(tiktok_posts[0].metadata["outfit_ids"]), 5)
                self.assertTrue(all(post.status == "scheduled" for post in pinterest_posts))
                self.assertEqual(
                    [post.published_at for post in pinterest_posts],
                    [
                        "2026-06-14T10:00-05:00",
                        "2026-06-14T12:00-05:00",
                        "2026-06-14T14:00-05:00",
                        "2026-06-14T16:00-05:00",
                        "2026-06-14T18:00-05:00",
                    ],
                )
            finally:
                conn.close()

    def test_create_local_publish_records_rejects_bad_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "publish.sqlite3"
            initialize_database(database_path)
            conn = connect(database_path)
            try:
                outfit = create_outfit(conn, concept_seed="x", spec={})
                with self.assertRaises(ValueError):
                    create_local_publish_records(
                        conn,
                        concept_id=None,
                        outfit=outfit,
                        products=[],
                        collage_path=Path("x.png"),
                        engagement_output={"tiktok": {}},
                    )
            finally:
                conn.close()

    def test_autopublish_posts_publishes_due_posts_and_skips_future_posts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            database_path = root / "publish.sqlite3"
            initialize_database(database_path)
            conn = connect(database_path)
            settings = Settings(
                app_env="test",
                log_level="WARNING",
                database_path=database_path,
                data_dir=root / "data",
                assets_dir=root / "assets",
                dry_run=False,
                ai_mode="claude",
                autoposting_enabled=True,
                public_asset_base_url="https://cdn.example.test/assets",
                tiktok_access_token="test-tiktok",
                pinterest_access_token="test-pinterest",
                pinterest_board_id="board_123",
            )
            try:
                outfits = [
                    create_outfit(
                        conn,
                        concept_seed="Bad Bunny concert",
                        spec={"outfit": {"title": f"Look {index}"}},
                    )
                    for index in range(1, 6)
                ]
                product = upsert_product(
                    conn,
                    retailer="Local Rack",
                    name="White Retro Sport Sunglasses",
                    category="accessory",
                    url="https://example.test/sunglasses",
                )
                engagement = {
                    "tiktok": {
                        "caption": "Five concert outfits.",
                        "hashtags": ["concertoutfit"],
                    },
                    "pinterest_posts": [
                        {
                            "title": f"Concert Outfit {index}",
                            "description": f"Look {index} for the concert.",
                            "hashtags": ["concert outfit"],
                        }
                        for index in range(1, 6)
                    ],
                }
                local = create_local_publish_records_for_outfit_set(
                    conn,
                    outfits=outfits,
                    products_by_outfit=[[product] for _ in outfits],
                    collage_paths=[Path(f"data/images/collages/look-{index}.png") for index in range(1, 6)],
                    engagement_output=engagement,
                    schedule_date_est="2026-06-14",
                )

                tiktok_client = FakeTikTokClient()
                pinterest_client = FakePinterestClient()
                result = autopublish_posts(
                    conn,
                    local.posts,
                    settings=settings,
                    now=datetime.fromisoformat("2026-06-14T13:00:00-05:00"),
                    tiktok_client=tiktok_client,
                    pinterest_client=pinterest_client,
                )
                conn.commit()

                self.assertEqual(len(result.published), 3)
                self.assertEqual(len(result.failed), 0)
                self.assertEqual(len(result.skipped), 3)
                self.assertEqual(len(tiktok_client.requests), 1)
                self.assertEqual(len(tiktok_client.requests[0]["image_urls"]), 5)
                self.assertEqual(len(pinterest_client.requests), 2)
                self.assertEqual(
                    pinterest_client.requests[0]["image_url"],
                    "https://cdn.example.test/assets/data/images/collages/look-1.png",
                )
                self.assertEqual(pinterest_client.requests[0]["link"], "https://example.test/sunglasses")

                stored = list_posts(conn, status="published")
                self.assertEqual(len(stored), 3)
                self.assertTrue(all(post.platform_post_id for post in stored))
            finally:
                conn.close()

    def test_autopublish_posts_fails_without_public_asset_base_url(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            database_path = root / "publish.sqlite3"
            initialize_database(database_path)
            conn = connect(database_path)
            settings = Settings(
                app_env="test",
                log_level="WARNING",
                database_path=database_path,
                data_dir=root / "data",
                assets_dir=root / "assets",
                dry_run=False,
                ai_mode="claude",
                autoposting_enabled=True,
                tiktok_access_token="test-tiktok",
                pinterest_access_token="test-pinterest",
                pinterest_board_id="board_123",
            )
            try:
                outfit = create_outfit(conn, concept_seed="x", spec={})
                local = create_local_publish_records(
                    conn,
                    outfit=outfit,
                    products=[],
                    collage_path=Path("data/images/collages/test.png"),
                    engagement_output=ENGAGEMENT_OUTPUT,
                )

                result = autopublish_posts(
                    conn,
                    local.posts,
                    settings=settings,
                    now=datetime.fromisoformat("2026-06-14T13:00:00-05:00"),
                    tiktok_client=FakeTikTokClient(),
                    pinterest_client=FakePinterestClient(),
                )

                self.assertEqual(len(result.published), 0)
                self.assertEqual(len(result.failed), 2)
                self.assertTrue(all("PUBLIC_ASSET_BASE_URL" in post.metadata["api_error"] for post in result.failed))
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
