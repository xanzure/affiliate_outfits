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
from app.pipelines.analytics_pipeline import apply_manual_metrics
from app.services.storage_service import StorageService
from app.utils.logging import configure_logging, get_logger


def main() -> None:
    parser = argparse.ArgumentParser(description="Record manual post metrics and update concept score.")
    parser.add_argument("file", type=Path, help="Path to a manual metrics JSON file.")
    args = parser.parse_args()

    settings = load_settings()
    configure_logging(settings.log_level)
    logger = get_logger(__name__)

    payload = json.loads(args.file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("manual metrics file must contain a JSON object")

    service = StorageService(settings)
    service.initialize()
    with service.connection() as conn:
        result = apply_manual_metrics(conn, payload)

    logger.info(
        "updated concept=%s score %.1f -> %.1f band=%s adjustment=%+.1f",
        result.concept.id,
        result.previous_score,
        result.concept.ranking_score,
        result.combined_metrics.performance_band,
        result.combined_metrics.score_adjustment,
    )
    if result.concept.status == "retired":
        logger.info("concept retired: %s", result.concept.seed)


if __name__ == "__main__":
    main()
