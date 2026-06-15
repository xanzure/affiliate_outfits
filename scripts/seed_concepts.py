from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from _bootstrap import add_project_root_to_path
except ModuleNotFoundError:
    from scripts._bootstrap import add_project_root_to_path

add_project_root_to_path()

from app.config import PROJECT_ROOT, load_settings
from app.creative_briefs import normalize_brief
from app.db.concepts import retire_active_concepts_not_in_seeds, upsert_concept
from app.services.storage_service import StorageService
from app.utils.logging import configure_logging, get_logger


DEFAULT_SEED_PATH = PROJECT_ROOT / "data/concepts/seed_concepts.json"


def seed_concepts(
    seed_path: Path = DEFAULT_SEED_PATH,
    *,
    settings=None,
    sync_active: bool = False,
) -> int:
    settings = settings or load_settings()
    configure_logging(settings.log_level)
    logger = get_logger(__name__)

    service = StorageService(settings)
    service.initialize()

    concepts = _load_seed_file(seed_path)
    seed_values: set[str] = set()
    with service.connection() as conn:
        for raw_concept in concepts:
            brief = normalize_brief(raw_concept)
            seed_values.add(brief.seed)
            upsert_concept(
                conn,
                brief.seed,
                source="seed",
                status=raw_concept.get("status", "active"),
                ranking_score=float(raw_concept.get("ranking_score", 50)),
                metadata={
                    "brief_schema_version": 1,
                    "brief": brief.payload,
                },
            )
        retired_count = retire_active_concepts_not_in_seeds(conn, seed_values) if sync_active else 0

    if len(concepts) != 8:
        logger.warning("seed file contains %s concepts; target active pool size is 8", len(concepts))
    logger.info("seeded %s concepts from %s", len(concepts), seed_path)
    if sync_active:
        logger.info("retired %s active concepts not present in seed file", retired_count)
    return len(concepts)


def _load_seed_file(seed_path: Path) -> list[dict]:
    value = json.loads(seed_path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError("seed concept file must contain a JSON array")
    if not all(isinstance(item, dict) for item in value):
        raise ValueError("seed concept file must contain only JSON objects")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed concepts into local storage.")
    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_SEED_PATH,
        help="Path to a JSON array of concepts.",
    )
    parser.add_argument(
        "--sync-active",
        action="store_true",
        help="Retire currently active concepts that are not present in the seed file.",
    )
    args = parser.parse_args()
    seed_concepts(args.file, sync_active=args.sync_active)


if __name__ == "__main__":
    main()
