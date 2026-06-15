import tempfile
import unittest
from pathlib import Path

from app.config import PROJECT_ROOT, load_settings
from app.utils.logging import configure_logging, get_logger


class FoundationTests(unittest.TestCase):
    def test_load_settings_defaults(self) -> None:
        settings = load_settings(env_file=Path("does-not-exist.env"))

        self.assertEqual(settings.app_env, "development")
        self.assertEqual(settings.log_level, "INFO")
        self.assertTrue(settings.dry_run)
        self.assertEqual(settings.ai_mode, "claude")
        self.assertEqual(settings.ai_provider, "anthropic")
        self.assertEqual(settings.anthropic_model, "claude-haiku-4-5")
        self.assertIsNone(settings.anthropic_api_key)
        self.assertEqual(settings.database_path, PROJECT_ROOT / "data/affiliate_outfits.sqlite3")

    def test_load_settings_from_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "APP_ENV=test",
                        "LOG_LEVEL=debug",
                        "DATABASE_PATH=/tmp/test.sqlite3",
                        "DATA_DIR=tmp-data",
                        "ASSETS_DIR=tmp-assets",
                        "DRY_RUN=false",
                        "AI_MODE=claude",
                        "AI_PROVIDER=anthropic",
                        "ANTHROPIC_MODEL=claude-test",
                        "ANTHROPIC_API_KEY=sk-ant-test",
                    ]
                ),
                encoding="utf-8",
            )

            settings = load_settings(env_file=env_file)

        self.assertEqual(settings.app_env, "test")
        self.assertEqual(settings.log_level, "DEBUG")
        self.assertEqual(settings.database_path, Path("/tmp/test.sqlite3"))
        self.assertEqual(settings.data_dir, PROJECT_ROOT / "tmp-data")
        self.assertEqual(settings.assets_dir, PROJECT_ROOT / "tmp-assets")
        self.assertFalse(settings.dry_run)
        self.assertEqual(settings.ai_mode, "claude")
        self.assertEqual(settings.ai_provider, "anthropic")
        self.assertEqual(settings.anthropic_model, "claude-test")
        self.assertEqual(settings.anthropic_api_key, "sk-ant-test")

    def test_configure_logging(self) -> None:
        configure_logging("WARNING")
        logger = get_logger("affiliate_outfits.test")

        self.assertEqual(logger.name, "affiliate_outfits.test")


if __name__ == "__main__":
    unittest.main()
