import tempfile
import unittest
from pathlib import Path

from app.collage.image_utils import write_solid_png
from app.config import Settings
from app.db.products import get_product, upsert_product
from app.pipelines.image_pipeline import prepare_product_images
from app.services.image_service import ImageService
from app.services.storage_service import connect, initialize_database


class ImagePipelineTests(unittest.TestCase):
    def test_prepare_product_images_generates_placeholder_and_updates_product(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            database_path = root / "images.sqlite3"
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
                product = upsert_product(
                    conn,
                    retailer="Local Rack",
                    name="Red Nylon Camp Collar Shirt",
                    category="top",
                    url="https://example.test/red-shirt",
                    metadata={"colors": ["red"]},
                )
                conn.commit()

                prepared = prepare_product_images(
                    conn,
                    [product],
                    image_service=ImageService(settings),
                )
                conn.commit()

                updated = get_product(conn, product.id)
                self.assertEqual(len(prepared), 1)
                self.assertTrue(prepared[0].normalized_path.exists())
                self.assertEqual(prepared[0].info.width, 800)
                self.assertEqual(prepared[0].info.height, 1000)
                self.assertEqual(updated.local_image_path, str(prepared[0].normalized_path))
            finally:
                conn.close()

    def test_prepare_product_images_downloads_product_image_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            database_path = root / "images.sqlite3"
            source_image = write_solid_png(root / "source.png", width=40, height=50, rgb=(1, 2, 3))
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
                product = upsert_product(
                    conn,
                    retailer="Local Rack",
                    name="Downloaded Product",
                    category="top",
                    url="https://example.test/downloaded",
                    image_url=source_image.as_uri(),
                )
                conn.commit()

                prepared = prepare_product_images(
                    conn,
                    [product],
                    image_service=ImageService(settings),
                )

                self.assertEqual(len(prepared), 1)
                self.assertTrue(prepared[0].normalized_path.exists())
                self.assertEqual(prepared[0].info.width, 40)
                self.assertEqual(prepared[0].info.height, 50)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
