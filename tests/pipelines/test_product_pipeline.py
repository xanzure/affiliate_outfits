import tempfile
import unittest
from pathlib import Path

from app.pipelines.product_pipeline import (
    ProductSearchSpec,
    resolve_products_from_searches,
    search_specs_from_agent_output,
)
from app.db.products import list_products
from app.services.product_search_service import ProductSearchResult
from app.services.storage_service import connect, initialize_database


class FakeProductSearchProvider:
    def search(
        self,
        query: str,
        *,
        category: str | None = None,
        limit: int = 5,
    ) -> list[ProductSearchResult]:
        return [
            ProductSearchResult(
                retailer="Good Store",
                name="Second Choice",
                url="https://good.example/second",
                category=category,
                price_cents=4200,
                source="test",
            ),
            ProductSearchResult(
                retailer="Good Store",
                name="First Choice",
                url="https://good.example/first",
                category=category,
                price_cents=2500,
                image_url="https://good.example/first.png",
                source="test",
            ),
            ProductSearchResult(
                retailer="Temu",
                name="Blocked Choice",
                url="https://temu.com/blocked",
                category=category,
                price_cents=100,
                source="test",
            ),
        ][:limit]


class ProductPipelineTests(unittest.TestCase):
    def test_search_specs_from_agent_output_accepts_strings_and_objects(self) -> None:
        specs = search_specs_from_agent_output(
            {
                "search_queries": [
                    "white sunglasses concert",
                    {"query": "black boots fall", "category": "shoe", "limit": 2},
                ]
            }
        )

        self.assertEqual(specs[0].query, "white sunglasses concert")
        self.assertIsNone(specs[0].category)
        self.assertEqual(specs[1].category, "shoe")
        self.assertEqual(specs[1].limit, 2)

    def test_search_specs_from_agent_output_rejects_bad_shape(self) -> None:
        with self.assertRaises(ValueError):
            search_specs_from_agent_output({"search_queries": {"query": "bad"}})

    def test_resolve_products_from_searches_stores_products(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "pipeline.sqlite3"
            initialize_database(database_path)
            conn = connect(database_path)
            try:
                products = resolve_products_from_searches(
                    conn,
                    [
                        ProductSearchSpec(
                            query="white statement concert sunglasses",
                            category="accessory",
                            limit=2,
                        )
                    ],
                    tracking_id="pipeline-test",
                    search_provider=FakeProductSearchProvider(),
                )
                conn.commit()

                stored_products = list_products(conn, category="accessory")
                self.assertEqual(len(products), 1)
                self.assertEqual(products[0].category, "accessory")
                self.assertEqual(products[0].name, "First Choice")
                self.assertIsNone(products[0].affiliate_url)
                self.assertEqual(len(stored_products), 2)
                self.assertEqual(stored_products[0].metadata["product_source"], "test")
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
