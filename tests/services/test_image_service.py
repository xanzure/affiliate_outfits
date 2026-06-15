import base64
import tempfile
import unittest
from pathlib import Path

from app.collage.background_removal import remove_background
from app.collage.image_utils import inspect_image, safe_image_filename, write_solid_png
from app.config import Settings
from app.services.image_service import ImageService


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


class ImageServiceTests(unittest.TestCase):
    def test_inspect_image_reads_png_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "tiny.png"
            image_path.write_bytes(PNG_1X1)

            info = inspect_image(image_path)

            self.assertEqual(info.image_type, "png")
            self.assertEqual(info.width, 1)
            self.assertEqual(info.height, 1)

    def test_inspect_image_rejects_unsupported_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "not-image.txt"
            image_path.write_text("nope", encoding="utf-8")

            with self.assertRaises(ValueError):
                inspect_image(image_path)

    def test_safe_image_filename_sanitizes_names(self) -> None:
        self.assertEqual(
            safe_image_filename(Path("Red Camp Collar Shirt!.PNG")),
            "Red-Camp-Collar-Shirt.png",
        )

    def test_prepare_local_image_copies_original_and_normalized_asset(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image_path = root / "source.png"
            image_path.write_bytes(PNG_1X1)
            settings = Settings(
                app_env="test",
                log_level="WARNING",
                database_path=root / "test.sqlite3",
                data_dir=root / "data",
                assets_dir=root / "assets",
                dry_run=True,
                ai_mode="claude",
            )

            prepared = ImageService(settings).prepare_local_image(
                image_path,
                asset_id="product_123",
            )

            self.assertTrue(prepared.original_path.exists())
            self.assertTrue(prepared.normalized_path.exists())
            self.assertEqual(prepared.info.width, 1)
            self.assertEqual(prepared.info.height, 1)

    def test_remove_background_falls_back_to_copy_without_rembg(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.png"
            destination = root / "out" / "source.png"
            source.write_bytes(PNG_1X1)

            output_path, removed = remove_background(source, destination, use_rembg=False)

            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.read_bytes(), PNG_1X1)
            if removed:
                self.assertNotEqual(output_path.read_bytes(), b"")

    def test_write_solid_png_creates_valid_image(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "solid.png"

            write_solid_png(image_path, width=12, height=8, rgb=(10, 20, 30))
            info = inspect_image(image_path)

            self.assertEqual(info.image_type, "png")
            self.assertEqual(info.width, 12)
            self.assertEqual(info.height, 8)


if __name__ == "__main__":
    unittest.main()
