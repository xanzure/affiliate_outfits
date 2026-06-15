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
from app.pipelines.daily_pipeline import run_daily_outfit_set_for_concept
from app.scheduler import select_concept_by_seed, select_daily_concept
from app.services.storage_service import StorageService
from app.services.json_response import parse_json_response
from app.utils.logging import configure_logging, get_logger


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local daily pipeline.")
    parser.add_argument("--count", type=int, default=1, help="Deprecated; daily runs now use 1 concept.")
    parser.add_argument("--limit", type=int, help="Deprecated alias for --count.")
    parser.add_argument(
        "--schedule-only",
        action="store_true",
        help="Only reserve briefs; do not run product/image/collage steps.",
    )
    parser.add_argument(
        "--outfit-response-file",
        type=Path,
        help="Path to a JSON file containing saved Outfit Agent batch output.",
    )
    parser.add_argument(
        "--engagement-response-file",
        type=Path,
        help="Path to a JSON file containing saved Engagement Agent output.",
    )
    parser.add_argument(
        "--skip-publish-records",
        action="store_true",
        help="Skip local TikTok/Pinterest draft record creation.",
    )
    parser.add_argument(
        "--seed",
        help="Reserve a specific active creative brief by seed text.",
    )
    args = parser.parse_args()

    settings = load_settings()
    configure_logging(settings.log_level)
    logger = get_logger(__name__)

    service = StorageService(settings)
    service.initialize()

    outfit_output = _load_json_output(args.outfit_response_file)
    engagement_output = _load_json_output(args.engagement_response_file)

    count = args.limit if args.limit is not None else args.count
    if count != 1:
        logger.warning("daily runs now select exactly 1 concept; ignoring requested count=%s", count)

    with service.connection() as conn:
        if args.seed:
            scheduled = select_concept_by_seed(conn, args.seed)
        else:
            scheduled = select_daily_concept(conn)

        if scheduled is None:
            logger.info("no active creative briefs available")
            return

        if not args.schedule_only:
            result = run_daily_outfit_set_for_concept(
                conn,
                scheduled,
                outfit_batch_output=outfit_output,
                engagement_output=engagement_output,
                create_publish_records=not args.skip_publish_records,
                settings=settings,
            )
            post_count = len(result.publish_result.posts) if result.publish_result else 0
            logger.info(
                "created concept_outfit_set outfits=%s posts=%s collages=%s",
                len(result.outfit_results),
                post_count,
                [str(item.collage_path) for item in result.outfit_results],
            )
            scheduled = result.scheduled_concept

    if scheduled:
        logger.info(
            "processed concept_id=%s usage_count=%s seed=%s",
            scheduled.concept_id,
            scheduled.usage_count,
            scheduled.seed,
        )


def _load_json_output(path: Path | None):
    if path is None:
        return None
    return parse_json_response(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
