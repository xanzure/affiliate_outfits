from __future__ import annotations

import argparse

try:
    from _bootstrap import add_project_root_to_path
except ModuleNotFoundError:
    from scripts._bootstrap import add_project_root_to_path

add_project_root_to_path()

from app.config import load_settings
from app.pipelines.publish_pipeline import process_queue_tick
from app.services.storage_service import StorageService
from app.utils.logging import configure_logging, get_logger


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run one queue cooldown tick (publish the head of each "
        "platform's queue if its 24h window has elapsed)."
    )
    parser.parse_args()

    settings = load_settings()
    configure_logging(settings.log_level)
    logger = get_logger(__name__)

    service = StorageService(settings)
    service.initialize()

    with service.connection() as conn:
        result = process_queue_tick(conn, settings=settings)

    logger.info(
        "autopublish complete published=%s failed=%s skipped=%s",
        len(result.published),
        len(result.failed),
        len(result.skipped),
    )


if __name__ == "__main__":
    main()
