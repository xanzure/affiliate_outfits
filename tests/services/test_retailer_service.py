import tempfile
import unittest
from pathlib import Path

from app.services.affiliate_service import LocalTrackingResolver, build_affiliate_link
from app.services.product_search_service import (
    ProductSearchResult,
    is_allowed_retailer,
    rank_product_results,
)
from app.services.retailer_service import (
    ProductFixture,
    load_product_fixtures,
    search_product_fixtures,
    store_product_matches,
)
from app.services.storage_service import connect, initialize_database


class RetailerServiceTests(unittest.TestCase):
    def test_build_affiliate_link_adds_tracking_params(self) -> None:
        link = build_affiliate_link(
            "https://example.test/product?color=red",
            network="local",
            tracking_id="test-id",
        )

        self.assertEqual(link.original_url, "https://example.test/product?color=red")
        self.assertIn("color=red", link.affiliate_url)
        self.assertIn("aff_network=local", link.affiliate_url)
        self.assertIn("aff_id=test-id", link.affiliate_url)

    def test_load_product_fixtures(self) -> None:
        fixtures = load_product_fixtures()

        self.assertGreaterEqual(len(fixtures), 1)
        self.assertEqual(fixtures[0].currency, "USD")

    def test_search_product_fixtures_scores_terms_and_category(self) -> None:
        fixtures = [
            ProductFixture(
                retailer="A",
                name="White Retro Sport Sunglasses",
                category="accessory",
                tags=["statement accessories", "concert"],
                colors=["white"],
                price_cents=2400,
                url="https://example.test/sunglasses",
            ),
            ProductFixture(
                retailer="A",
                name="Plain White Tee",
                category="top",
                tags=["basic"],
                colors=["white"],
                price_cents=1200,
                url="https://example.test/tee",
            ),
        ]

        matches = search_product_fixtures(
            "white statement concert sunglasses",
            category="accessory",
            fixtures=fixtures,
        )

        self.assertEqual(matches[0].fixture.name, "White Retro Sport Sunglasses")
        self.assertIn("white", matches[0].matched_terms)
        self.assertIn("concert", matches[0].matched_terms)

    def test_store_product_matches_upserts_products(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "products.sqlite3"
            initialize_database(database_path)
            conn = connect(database_path)
            try:
                fixtures = [
                    ProductFixture(
                        retailer="A",
                        name="Black Lug Sole Ankle Boot",
                        category="shoe",
                        tags=["black boots", "fall"],
                        colors=["black"],
                        price_cents=6900,
                        url="https://example.test/boot",
                    )
                ]
                matches = search_product_fixtures(
                    "black boots fall",
                    category="shoe",
                    fixtures=fixtures,
                )

                products = store_product_matches(conn, matches, tracking_id="unit-test")
                conn.commit()

                self.assertEqual(len(products), 1)
                self.assertEqual(products[0].category, "shoe")
                self.assertIsNone(products[0].affiliate_url)
                self.assertEqual(products[0].metadata["match_score"], matches[0].score)
            finally:
                conn.close()

    def test_store_product_matches_can_use_local_tracking_resolver(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "tracked.sqlite3"
            initialize_database(database_path)
            conn = connect(database_path)
            try:
                fixtures = [
                    ProductFixture(
                        retailer="A",
                        name="Black Lug Sole Ankle Boot",
                        category="shoe",
                        tags=["black boots"],
                        colors=["black"],
                        price_cents=6900,
                        url="https://example.test/boot",
                    )
                ]
                matches = search_product_fixtures("black boots", fixtures=fixtures)

                products = store_product_matches(
                    conn,
                    matches,
                    affiliate_resolver=LocalTrackingResolver(),
                    tracking_id="unit-test",
                )

                self.assertIn("aff_id=unit-test", products[0].affiliate_url)
            finally:
                conn.close()

    def test_retailer_policy_blocks_suspicious_retailers_but_allows_shein_accessories(self) -> None:
        self.assertFalse(is_allowed_retailer("Temu", "https://temu.com/item", category="top"))
        self.assertFalse(is_allowed_retailer("SHEIN", "https://shein.com/dress", category="dress"))
        self.assertTrue(is_allowed_retailer("SHEIN", "https://shein.com/hat", category="hat"))

    def test_rank_product_results_prefers_cheaper_safe_items(self) -> None:
        ranked = rank_product_results(
            [
                ProductSearchResult(
                    retailer="Good Store",
                    name="Expensive Hat",
                    url="https://good.example/expensive",
                    category="hat",
                    price_cents=3000,
                ),
                ProductSearchResult(
                    retailer="Good Store",
                    name="Cheap Hat",
                    url="https://good.example/cheap",
                    category="hat",
                    price_cents=1200,
                ),
                ProductSearchResult(
                    retailer="Temu",
                    name="Very Cheap Hat",
                    url="https://temu.com/cheap",
                    category="hat",
                    price_cents=100,
                ),
            ],
            category="hat",
        )

        self.assertEqual([item.name for item in ranked], ["Cheap Hat", "Expensive Hat"])


if __name__ == "__main__":
    unittest.main()
