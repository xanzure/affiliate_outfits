import tempfile
import unittest
from pathlib import Path

from app.db.concepts import create_concept, get_concept, update_concept_metadata
from app.pipelines.daily_pipeline import _set_concept_cover_image_if_missing
from app.services.storage_service import connect, initialize_database

URL = "https://example.supabase.co/storage/v1/object/public/collages/look-1.png"
LOCAL = "/home/someone/project/data/images/collages/look-1.png"


class ConceptCoverTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        database_path = Path(self._tmp.name) / "cover.sqlite3"
        initialize_database(database_path)
        self.conn = connect(database_path)
        self.concept = create_concept(self.conn, "Dark academia", metadata={"brief": {"seed": "Dark academia"}})

    def tearDown(self) -> None:
        self.conn.close()
        self._tmp.cleanup()

    def _cover(self) -> str | None:
        return get_concept(self.conn, self.concept.id).metadata.get("cover_image_url")

    def _seed_cover(self, value: str) -> None:
        update_concept_metadata(self.conn, self.concept.id, {**self.concept.metadata, "cover_image_url": value})

    def test_sets_cover_when_missing(self) -> None:
        _set_concept_cover_image_if_missing(self.conn, self.concept.id, URL)
        self.assertEqual(self._cover(), URL)

    def test_public_url_replaces_a_stale_local_path(self) -> None:
        self._seed_cover(LOCAL)
        _set_concept_cover_image_if_missing(self.conn, self.concept.id, URL)
        self.assertEqual(self._cover(), URL)

    def test_keeps_an_existing_public_url(self) -> None:
        self._seed_cover(URL)
        _set_concept_cover_image_if_missing(self.conn, self.concept.id, "https://example.test/other.png")
        self.assertEqual(self._cover(), URL)

    def test_local_path_never_overwrites_a_public_url(self) -> None:
        self._seed_cover(URL)
        _set_concept_cover_image_if_missing(self.conn, self.concept.id, LOCAL)
        self.assertEqual(self._cover(), URL)


if __name__ == "__main__":
    unittest.main()
