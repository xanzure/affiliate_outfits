import unittest

from app.agents.outfit.parser import normalize_outfit_agent_output, validate_outfit_agent_output


VALID_OUTFIT_RESPONSE = {
    "interpretation": {
        "primary_reference": "Bad Bunny",
        "used_cues": ["concert", "statement accessories"],
        "discarded_cues": [],
        "rationale": "Uses music-event styling and brief-specific accessory cues.",
    },
    "outfit": {
        "title": "Concert Streetwear",
        "categories": ["top", "bottom", "accessory"],
        "colors": ["red", "white", "blue"],
        "materials": ["cotton"],
        "accessories": ["statement sunglasses"],
    },
    "search_queries": [
        {"query": "red concert streetwear top", "category": "top", "limit": 1},
        "white statement sunglasses",
    ],
    "diversity_notes": ["Kept the concept specific."],
}


class OutfitParserTests(unittest.TestCase):
    def test_normalize_outfit_agent_output_accepts_valid_response(self) -> None:
        normalized = normalize_outfit_agent_output(VALID_OUTFIT_RESPONSE)

        self.assertEqual(normalized["interpretation"]["primary_reference"], "Bad Bunny")
        self.assertEqual(normalized["search_queries"][0]["limit"], 1)
        self.assertEqual(normalized["search_queries"][1]["query"], "white statement sunglasses")
        self.assertIsNone(normalized["search_queries"][1]["category"])

    def test_validate_outfit_agent_output_rejects_missing_interpretation(self) -> None:
        invalid = dict(VALID_OUTFIT_RESPONSE)
        invalid.pop("interpretation")

        with self.assertRaisesRegex(ValueError, "missing required field 'interpretation'"):
            validate_outfit_agent_output(invalid)

    def test_validate_outfit_agent_output_rejects_empty_search_queries(self) -> None:
        invalid = dict(VALID_OUTFIT_RESPONSE)
        invalid["search_queries"] = []

        with self.assertRaisesRegex(ValueError, "at least one query"):
            validate_outfit_agent_output(invalid)

    def test_validate_outfit_agent_output_rejects_bad_limit(self) -> None:
        invalid = dict(VALID_OUTFIT_RESPONSE)
        invalid["search_queries"] = [{"query": "top", "limit": 0}]

        with self.assertRaisesRegex(ValueError, "limit"):
            validate_outfit_agent_output(invalid)


if __name__ == "__main__":
    unittest.main()
