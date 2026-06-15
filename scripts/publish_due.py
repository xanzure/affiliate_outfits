from __future__ import annotations

import argparse

try:
    from _bootstrap import add_project_root_to_path
except ModuleNotFoundError:
    from scripts._bootstrap import add_project_root_to_path

add_project_root_to_path()

from app.config import load_settings
from app.pipelines.publish_pipeline import autopublish_due_posts
from app.services.storage_service import StorageService
from app.utils.logging import configure_logging, get_logger


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish due TikTok/Pinterest posts.")
    parser.parse_args()

    settings = load_settings()
    configure_logging(settings.log_level)
    logger = get_logger(__name__)

    service = StorageService(settings)
    service.initialize()

    with service.connection() as conn:
        result = autopublish_due_posts(conn, settings=settings)

    logger.info(
        "autopublish complete published=%s failed=%s skipped=%s",
        len(result.published),
        len(result.failed),
        len(result.skipped),
    )


if __name__ == "__main__":
    main()
