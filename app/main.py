from __future__ import annotations

from app.config import load_settings
from app.utils.logging import configure_logging, get_logger


def main() -> None:
    settings = load_settings()
    configure_logging(settings.log_level)

    logger = get_logger(__name__)
    logger.info("Affiliate Outfits starting")
    logger.info(
        "environment=%s dry_run=%s ai_mode=%s",
        settings.app_env,
        settings.dry_run,
        settings.ai_mode,
    )
    logger.info("database_path=%s", settings.database_path)


if __name__ == "__main__":
    main()
