import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.db.collages import create_collage, list_collages_for_outfit
from app.db.metrics import latest_metrics_for_post, record_metrics
from app.db.outfits import create_outfit, list_outfits_for_concept
from app.db.posts import create_post, update_post_status
from app.db.products import list_products, upsert_product
from app.db.concepts import (
    create_concept,
    get_concept,
    list_active_concepts,
    mark_concept_posted,
    retire_concept,
    update_concept_metadata,
)
from app.db.outfits import update_outfit_spec
from app.services.storage_service import StorageService, connect, initialize_database


class StorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "storage.sqlite3"
        initialize_database(self.database_path)
        self.conn = connect(self.database_path)

    def tearDown(self) -> None:
        self.conn.close()
        self.temp_dir.cleanup()

    def test_concept_lifecycle(self) -> None:
        concept = create_concept(self.conn, "minimal linen summer outfit")
        self.conn.commit()

        active_concepts = list_active_concepts(self.conn)
        self.assertEqual([item.id for item in active_concepts], [concept.id])

        used_concept = mark_concept_posted(self.conn, concept.id, posted_date_est="2026-06-14")
        self.assertEqual(used_concept.usage_count, 1)
        self.assertEqual(used_concept.last_posted_date_est, "2026-06-14")

        retired_concept = retire_concept(self.conn, concept.id)
        self.assertEqual(retired_concept.status, "retired")
        self.assertEqual(list_active_concepts(self.conn), [])

    def test_product_outfit_post_and_metrics_flow(self) -> None:
        concept = create_concept(self.conn, "city weekend outfit")
        product = upsert_product(
            self.conn,
            retailer="Example Retailer",
            name="White Tee",
            category="top",
            url="https://example.test/products/white-tee",
            affiliate_url="https://affiliate.test/white-tee",
            price_cents=2800,
            metadata={"color": "white"},
        )
        outfit = create_outfit(
            self.conn,
            concept_id=concept.id,
            concept_seed=concept.seed,
            product_ids=[product.id],
            spec={"aesthetic": "minimal", "items": ["white tee"]},
        )
        post = create_post(
            self.conn,
            concept_id=concept.id,
            outfit_id=outfit.id,
            platform="local",
            image_path="data/images/example.png",
            caption="Weekend basics.",
        )
        published_post = update_post_status(
            self.conn,
            post.id,
            status="published",
            platform_post_id="local_123",
            published_at="2026-06-14T00:00:00+00:00",
        )
        metric = record_metrics(
            self.conn,
            post_id=post.id,
            platform="local",
            views=100,
            likes=10,
            comments=2,
            shares=3,
            saves=4,
            clicks=5,
            score=24.5,
        )
        self.conn.commit()

        self.assertEqual(product.metadata["color"], "white")
        self.assertEqual(list_products(self.conn, category="top")[0].id, product.id)
        self.assertEqual(list_outfits_for_concept(self.conn, concept.id)[0].id, outfit.id)
        self.assertEqual(published_post.status, "published")
        self.assertEqual(metric.score, 24.5)
        self.assertEqual(latest_metrics_for_post(self.conn, post.id).id, metric.id)

    def test_collage_layout_is_stored_for_outfit_recreation(self) -> None:
        outfit = create_outfit(
            self.conn,
            concept_seed="city weekend outfit",
            product_ids=["product_1"],
            spec={"outfit": {"title": "City Weekend"}},
        )
        collage = create_collage(
            self.conn,
            outfit_id=outfit.id,
            image_path="data/images/collages/outfit.png",
            layout={
                "canvas": {"width": 1080, "height": 1350},
                "pieces": [
                    {
                        "index": 0,
                        "product_id": "product_1",
                        "image_path": "data/images/normalized/product_1.png",
                        "x": 80,
                        "y": 80,
                        "width": 920,
                        "height": 1190,
                    }
                ],
            },
        )
        self.conn.commit()

        stored = list_collages_for_outfit(self.conn, outfit.id)[0]

        self.assertEqual(stored.id, collage.id)
        self.assertEqual(stored.layout["pieces"][0]["product_id"], "product_1")
        self.assertEqual(stored.layout["pieces"][0]["x"], 80)

    def test_outfit_spec_and_concept_metadata_can_be_updated_for_website(self) -> None:
        concept = create_concept(self.conn, "website concept", metadata={"brief": {"seed": "website concept"}})
        outfit = create_outfit(
            self.conn,
            concept_id=concept.id,
            concept_seed=concept.seed,
            spec={"outfit": {"title": "Website Outfit"}},
        )

        updated_outfit = update_outfit_spec(
            self.conn,
            outfit.id,
            {
                **outfit.spec,
                "layout": [
                    {
                        "product_id": "product_1",
                        "x": 7.4074,
                        "y": 5.9259,
                        "width": 42.0,
                        "rotation": 0,
                        "z_index": 1,
                    }
                ],
            },
        )
        updated_concept = update_concept_metadata(
            self.conn,
            concept.id,
            {**concept.metadata, "cover_image_url": "data/images/collages/cover.png"},
        )
        self.conn.commit()

        self.assertEqual(updated_outfit.spec["layout"][0]["product_id"], "product_1")
        self.assertEqual(updated_concept.metadata["cover_image_url"], "data/images/collages/cover.png")
        self.assertEqual(
            get_concept(self.conn, concept.id).metadata["cover_image_url"],
            "data/images/collages/cover.png",
        )

    def test_foreign_keys_are_enforced(self) -> None:
        with self.assertRaises(sqlite3.IntegrityError):
            create_outfit(
                self.conn,
                concept_id="missing",
                concept_seed="missing concept",
                spec={},
            )

    def test_storage_service_commits_context(self) -> None:
        service = StorageService()
        # Force the local sqlite path so the test stays hermetic (no live Supabase).
        service._supabase_db_url = None
        service.database_path = self.database_path

        with service.connection() as conn:
            concept = create_concept(conn, "committed concept")

        with connect(self.database_path) as conn:
            active_concepts = list_active_concepts(conn)

        self.assertEqual(active_concepts[0].id, concept.id)


if __name__ == "__main__":
    unittest.main()
