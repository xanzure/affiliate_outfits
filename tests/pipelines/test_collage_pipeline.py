import tempfile
import unittest
from pathlib import Path

from app.collage.export import export_collage
from app.collage.image_utils import inspect_image, write_solid_png
from app.collage.layout import Canvas, fixed_grid_layout
from app.config import Settings
from app.pipelines.collage_pipeline import render_collage_for_images
from app.services.image_service import ImageService


class CollagePipelineTests(unittest.TestCase):
    def test_fixed_grid_layout_creates_expected_cells(self) -> None:
        layout = fixed_grid_layout(
            3,
            canvas=Canvas(width=1000, height=1000, padding=100, gap=20),
        )

        self.assertEqual(len(layout.placements), 3)
        self.assertEqual(layout.placements[0].x, 100)
        self.assertEqual(layout.placements[0].y, 100)
        self.assertEqual(layout.placements[1].x, 510)
        self.assertEqual(layout.placements[2].y, 510)

    def test_export_collage_writes_fixed_editorial_canvas_png(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = write_solid_png(root / "first.png", width=100, height=100, rgb=(255, 0, 0))
            second = write_solid_png(root / "second.png", width=100, height=100, rgb=(0, 0, 255))
            output = root / "collage.png"

            # The renderer composes onto a fixed 1080x1350 editorial canvas.
            export_collage([first, second], output)
            info = inspect_image(output)

            self.assertEqual(info.width, 1080)
            self.assertEqual(info.height, 1350)

    def test_render_collage_for_images_uses_prepared_images(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image = write_solid_png(root / "product.png", width=100, height=100, rgb=(10, 20, 30))
            settings = Settings(
                app_env="test",
                log_level="WARNING",
                database_path=root / "test.sqlite3",
                data_dir=root / "data",
                assets_dir=root / "assets",
                dry_run=True,
                ai_mode="claude",
            )
            prepared = ImageService(settings).prepare_local_image(image, asset_id="product_1")

            output = render_collage_for_images(
                [prepared],
                output_name="test-collage.png",
                settings=settings,
            )
            info = inspect_image(output)

            self.assertEqual(info.width, 1080)
            self.assertEqual(info.height, 1350)


if __name__ == "__main__":
    unittest.main()
