import tempfile
import unittest
from pathlib import Path

from app.db.concepts import create_concept, retire_concept
from app.pipelines.concept_replacement_pipeline import (
    create_replacement_concept,
    normalize_replacement_brief,
)
from app.services.storage_service import connect, initialize_database


VALID_BRIEF = {
    "seed": "Rainy gallery opening outfit",
    "subject": "gallery opening",
    "occasion": "rainy evening",
    "context_notes": ["Urban art crowd, practical rain-aware styling"],
    "style_cues": ["sleek trench", "structured bag"],
    "color_cues": ["black", "silver"],
    "required_considerations": ["Keep shoes walkable"],
    "avoid": ["fragile fabrics"],
}


class ConceptReplacementPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "replacement.sqlite3"
        initialize_database(self.database_path)
        self.conn = connect(self.database_path)

    def tearDown(self) -> None:
        self.conn.close()
        self.temp_dir.cleanup()

    def test_create_replacement_concept_stores_needs_review_at_score_50(self) -> None:
        retired = create_concept(self.conn, "Retired low performer", ranking_score=20)
        retired = retire_concept(self.conn, retired.id)

        replacement = create_replacement_concept(
            self.conn,
            retired_concept_id=retired.id,
            replacement_brief=VALID_BRIEF,
        )
        self.conn.commit()

        self.assertEqual(replacement.status, "needs_review")
        self.assertEqual(replacement.ranking_score, 50)
        self.assertEqual(replacement.source, "replacement")
        self.assertEqual(replacement.metadata["replaces_concept_id"], retired.id)
        self.assertEqual(replacement.metadata["brief"]["seed"], VALID_BRIEF["seed"])

    def test_create_replacement_concept_rejects_active_concept(self) -> None:
        active = create_concept(self.conn, "Still active")

        with self.assertRaises(ValueError):
            create_replacement_concept(
                self.conn,
                retired_concept_id=active.id,
                replacement_brief=VALID_BRIEF,
            )

    def test_normalize_replacement_brief_requires_nuanced_lists(self) -> None:
        invalid = dict(VALID_BRIEF)
        invalid["context_notes"] = []

        with self.assertRaises(ValueError):
            normalize_replacement_brief(invalid)


if __name__ == "__main__":
    unittest.main()
