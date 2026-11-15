import unittest

from app.pipelines.daily_pipeline import _spec_with_website_layout

MANIFEST = {
    "canvas": {"width": 1080, "height": 1350},
    "pieces": [
        {"product_id": "p_top", "x": 324, "y": 92, "width": 432, "height": 460, "rotation": 0, "z_index": 3},
        {"product_id": "p_shoe", "x": 64, "y": 672, "width": 183, "height": 218, "rotation": -11, "z_index": 4},
        {"x": 1, "y": 1, "width": 1, "height": 1},  # no product id → skipped
    ],
}
URL = "https://example.supabase.co/storage/v1/object/public/collages/look.png"


class WebsiteLayoutTests(unittest.TestCase):
    def test_boxes_are_percent_of_full_canvas_including_height(self) -> None:
        spec = _spec_with_website_layout({"template": "classic_5"}, MANIFEST, URL)
        top, shoe = spec["layout"]
        self.assertEqual(top, {
            "product_id": "p_top", "x": 30.0, "y": 6.8148, "width": 40.0,
            "rotation": 0.0, "z_index": 3, "height": 34.0741,
        })
        self.assertEqual(shoe["height"], 16.1481)
        self.assertEqual(shoe["rotation"], -11.0)
        self.assertEqual(spec["template"], "classic_5")

    def test_stores_public_collage_url(self) -> None:
        self.assertEqual(_spec_with_website_layout({}, MANIFEST, URL)["collage_url"], URL)

    def test_drops_stale_url_when_new_render_has_none(self) -> None:
        # A re-render without an upload must not leave the old image paired with
        # the new layout.
        spec = _spec_with_website_layout({"collage_url": URL}, MANIFEST, None)
        self.assertNotIn("collage_url", spec)
        spec = _spec_with_website_layout({"collage_url": URL}, MANIFEST, "data/images/collages/x.png")
        self.assertNotIn("collage_url", spec)

    def test_legacy_pieces_without_height_still_convert(self) -> None:
        manifest = {"canvas": {"width": 1000, "height": 1000},
                    "pieces": [{"product_id": "p", "x": 100, "y": 200, "width": 300}]}
        (item,) = _spec_with_website_layout({}, manifest)["layout"]
        self.assertNotIn("height", item)
        self.assertEqual((item["x"], item["y"], item["width"]), (10.0, 20.0, 30.0))


if __name__ == "__main__":
    unittest.main()
