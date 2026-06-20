from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")

    return values


def _get_bool(value: str) -> bool:
    return value.lower() in {"1", "true", "yes", "on"}


def _resolve_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


@dataclass(frozen=True)
class Settings:
    app_env: str
    log_level: str
    database_path: Path
    data_dir: Path
    assets_dir: Path
    dry_run: bool
    ai_mode: str = "claude"
    ai_provider: str = "anthropic"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-haiku-4-5"
    product_search_provider: str = "fixtures"
    serpapi_api_key: str | None = None
    tavily_api_key: str | None = None
    runflow_api_key: str | None = None
    google_shopping_location: str = "United States"
    google_shopping_gl: str = "us"
    google_shopping_hl: str = "en"
    affiliate_provider: str = "none"
    awin_oauth2_token: str | None = None
    awin_publisher_id: str | None = None
    autoposting_enabled: bool = False
    public_asset_base_url: str | None = None
    tiktok_client_key: str | None = None
    tiktok_client_secret: str | None = None
    tiktok_access_token: str | None = None
    tiktok_refresh_token: str | None = None
    tiktok_post_mode: str = "DIRECT_POST"
    tiktok_privacy_level: str = "SELF_ONLY"
    tiktok_disable_comment: bool = False
    tiktok_auto_add_music: bool = True
    tiktok_brand_content_toggle: bool = False
    tiktok_brand_organic_toggle: bool = False
    pinterest_client_id: str | None = None
    pinterest_client_secret: str | None = None
    pinterest_access_token: str | None = None
    pinterest_refresh_token: str | None = None
    pinterest_board_id: str | None = None
    supabase_db_url: str | None = None

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


def load_settings(env_file: Path | None = None) -> Settings:
    env_values = _load_env_file(env_file or PROJECT_ROOT / ".env")

    def read(key: str, default: str) -> str:
        return os.environ.get(key, env_values.get(key, default))

    data_dir = _resolve_path(read("DATA_DIR", "data"))
    assets_dir = _resolve_path(read("ASSETS_DIR", "app/assets"))

    return Settings(
        app_env=read("APP_ENV", "development"),
        log_level=read("LOG_LEVEL", "INFO").upper(),
        database_path=_resolve_path(read("DATABASE_PATH", "data/affiliate_outfits.sqlite3")),
        data_dir=data_dir,
        assets_dir=assets_dir,
        dry_run=_get_bool(read("DRY_RUN", "true")),
        ai_mode=read("AI_MODE", "claude"),
        ai_provider=read("AI_PROVIDER", "anthropic"),
        anthropic_api_key=read("ANTHROPIC_API_KEY", "") or None,
        anthropic_model=read("ANTHROPIC_MODEL", "claude-haiku-4-5"),
        product_search_provider=read("PRODUCT_SEARCH_PROVIDER", "fixtures").lower(),
        serpapi_api_key=read("SERPAPI_API_KEY", "") or None,
        tavily_api_key=read("TAVILY_API_KEY", "") or None,
        runflow_api_key=read("RUNFLOW_API_KEY", "") or None,
        google_shopping_location=read("GOOGLE_SHOPPING_LOCATION", "United States"),
        google_shopping_gl=read("GOOGLE_SHOPPING_GL", "us"),
        google_shopping_hl=read("GOOGLE_SHOPPING_HL", "en"),
        affiliate_provider=read("AFFILIATE_PROVIDER", "none").lower(),
        awin_oauth2_token=read("AWIN_OAUTH2_TOKEN", "") or None,
        awin_publisher_id=read("AWIN_PUBLISHER_ID", "") or None,
        autoposting_enabled=_get_bool(read("AUTOPOSTING_ENABLED", "false")),
        public_asset_base_url=read("PUBLIC_ASSET_BASE_URL", "").rstrip("/") or None,
        tiktok_client_key=read("TIKTOK_CLIENT_KEY", "") or None,
        tiktok_client_secret=read("TIKTOK_CLIENT_SECRET", "") or None,
        tiktok_access_token=read("TIKTOK_ACCESS_TOKEN", "") or None,
        tiktok_refresh_token=read("TIKTOK_REFRESH_TOKEN", "") or None,
        tiktok_post_mode=read("TIKTOK_POST_MODE", "DIRECT_POST"),
        tiktok_privacy_level=read("TIKTOK_PRIVACY_LEVEL", "SELF_ONLY"),
        tiktok_disable_comment=_get_bool(read("TIKTOK_DISABLE_COMMENT", "false")),
        tiktok_auto_add_music=_get_bool(read("TIKTOK_AUTO_ADD_MUSIC", "true")),
        tiktok_brand_content_toggle=_get_bool(read("TIKTOK_BRAND_CONTENT_TOGGLE", "false")),
        tiktok_brand_organic_toggle=_get_bool(read("TIKTOK_BRAND_ORGANIC_TOGGLE", "false")),
        pinterest_client_id=read("PINTEREST_CLIENT_ID", "") or None,
        pinterest_client_secret=read("PINTEREST_CLIENT_SECRET", "") or None,
        pinterest_access_token=read("PINTEREST_ACCESS_TOKEN", "") or None,
        pinterest_refresh_token=read("PINTEREST_REFRESH_TOKEN", "") or None,
        pinterest_board_id=read("PINTEREST_BOARD_ID", "") or None,
        supabase_db_url=read("SUPABASE_DB_URL", "") or None,
    )
