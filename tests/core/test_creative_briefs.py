import unittest

from app.creative_briefs import brief_from_concept_metadata, normalize_brief, validate_brief


class CreativeBriefTests(unittest.TestCase):
    def test_normalize_brief_trims_seed_and_lists(self) -> None:
        brief = normalize_brief(
            {
                "seed": "  Bad Bunny summer concert outfit  ",
                "context_notes": [" Puerto Rican cultural references are relevant ", ""],
                "style_cues": ["streetwear"],
                "avoid": ["costume styling"],
            }
        )

        self.assertEqual(brief.seed, "Bad Bunny summer concert outfit")
        self.assertEqual(
            brief.payload["context_notes"],
            ["Puerto Rican cultural references are relevant"],
        )

    def test_validate_brief_requires_seed(self) -> None:
        with self.assertRaises(ValueError):
            validate_brief({"style_cues": []})

    def test_validate_brief_requires_list_fields_to_be_lists(self) -> None:
        with self.assertRaises(ValueError):
            validate_brief({"seed": "x", "style_cues": "streetwear"})

    def test_brief_from_concept_metadata_falls_back_to_seed(self) -> None:
        self.assertEqual(brief_from_concept_metadata("fallback seed", {}), {"seed": "fallback seed"})


if __name__ == "__main__":
    unittest.main()
