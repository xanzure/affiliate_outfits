from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from _bootstrap import add_project_root_to_path
except ModuleNotFoundError:
    from scripts._bootstrap import add_project_root_to_path

add_project_root_to_path()

from app.config import load_settings
from app.pipelines.concept_replacement_pipeline import create_replacement_concept
from app.services.storage_service import StorageService
from app.services.json_response import parse_json_response
from app.utils.logging import configure_logging, get_logger


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a needs-review replacement concept.")
    parser.add_argument("retired_concept_id", help="Retired concept ID to replace.")
    parser.add_argument(
        "--response-file",
        type=Path,
        help="Optional JSON file containing a saved Prompt Agent response.",
    )
    parser.add_argument("--notes", help="Optional guidance to include in the Prompt Agent request.")
    args = parser.parse_args()

    settings = load_settings()
    configure_logging(settings.log_level)
    logger = get_logger(__name__)

    replacement_brief = None
    if args.response_file:
        replacement_brief = parse_json_response(args.response_file.read_text(encoding="utf-8"))

    service = StorageService(settings)
    service.initialize()
    with service.connection() as conn:
        concept = create_replacement_concept(
            conn,
            retired_concept_id=args.retired_concept_id,
            replacement_brief=replacement_brief,
            user_notes=args.notes,
        )

    logger.info(
        "created replacement concept=%s status=%s score=%.1f seed=%s",
        concept.id,
        concept.status,
        concept.ranking_score,
        concept.seed,
    )


if __name__ == "__main__":
    main()
