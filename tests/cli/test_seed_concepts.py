import tempfile
import unittest
from pathlib import Path

from app.config import load_settings
from app.db.concepts import create_concept, list_active_concepts
from app.services.storage_service import connect, initialize_database
from scripts.seed_concepts import seed_concepts


class SeedConceptsTests(unittest.TestCase):
    def test_seed_concepts_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            database_path = temp_path / "seed.sqlite3"
            env_file = temp_path / ".env"
            seed_file = temp_path / "seed_concepts.json"
            env_file.write_text(
                "\n".join(
                    [
                        "APP_ENV=test",
                        "LOG_LEVEL=WARNING",
                        f"DATABASE_PATH={database_path}",
                        "DATA_DIR=data",
                        "ASSETS_DIR=app/assets",
                        "DRY_RUN=true",
                        "AI_MODE=claude",
                    ]
                ),
                encoding="utf-8",
            )
            seed_file.write_text(
                "["
                + ",".join(
                    [
                        """
  {
    "seed": "Concept %s",
    "context_notes": ["Seeded concept"],
    "style_cues": ["style"],
    "avoid": ["duplicate concept"]
  }
"""
                        % index
                        for index in range(1, 9)
                    ]
                )
                + "]",
                encoding="utf-8",
            )

            settings = load_settings(env_file=env_file)
            initialize_database(settings.database_path)

            seed_concepts(seed_file, settings=settings)
            seed_concepts(seed_file, settings=settings)

            with connect(database_path) as conn:
                concepts = list_active_concepts(conn)

            self.assertEqual(len(concepts), 8)
            self.assertEqual(concepts[0].ranking_score, 50)

    def test_seed_concepts_can_sync_active_pool(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            database_path = temp_path / "seed.sqlite3"
            env_file = temp_path / ".env"
            seed_file = temp_path / "seed_concepts.json"
            env_file.write_text(
                "\n".join(
                    [
                        "APP_ENV=test",
                        "LOG_LEVEL=WARNING",
                        f"DATABASE_PATH={database_path}",
                        "DATA_DIR=data",
                        "ASSETS_DIR=app/assets",
                        "DRY_RUN=true",
                        "AI_MODE=claude",
                    ]
                ),
                encoding="utf-8",
            )
            seed_file.write_text(
                '[{"seed": "Concept A"}, {"seed": "Concept B"}]',
                encoding="utf-8",
            )

            settings = load_settings(env_file=env_file)
            initialize_database(settings.database_path)
            with connect(database_path) as conn:
                create_concept(conn, "Stale active concept")
                conn.commit()

            seed_concepts(seed_file, settings=settings, sync_active=True)

            with connect(database_path) as conn:
                active_seeds = {concept.seed for concept in list_active_concepts(conn)}

            self.assertEqual(active_seeds, {"Concept A", "Concept B"})


if __name__ == "__main__":
    unittest.main()
