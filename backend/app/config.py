from __future__ import annotations

import os
import sys
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent


def _default_data_dir() -> Path:
    override = os.environ.get("CRAWLER_DATA_DIR")
    if override:
        return Path(override)
    return BASE_DIR / "data"


DATA_DIR = _default_data_dir()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CRAWLER_",
        env_file=(".env", BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = f"sqlite+aiosqlite:///{DATA_DIR / 'crawler.db'}"
    user_agent: str = "SEOScreamingLinkBuilding/1.0 (+https://stivmartinez.com; first-party SEO analysis)"
    request_timeout: float = 15.0
    max_response_bytes: int = 5_000_000
    default_concurrency: int = 4
    default_delay_seconds: float = 0.25
    default_max_pages: int = 10_000
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    static_dir: str | None = None

    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


def resolve_static_dir() -> Path | None:
    settings_static = settings.static_dir
    candidates: list[Path] = []
    if settings_static:
        candidates.append(Path(settings_static))
    if getattr(sys, "frozen", False):
        meipass = Path(getattr(sys, "_MEIPASS", ""))
        candidates.append(meipass / "static")
    candidates.extend(
        (
            BASE_DIR / "static",
            REPO_ROOT / "frontend" / "dist",
        )
    )
    for path in candidates:
        if path and (path / "index.html").is_file():
            return path
    return None


settings = Settings()
DATA_DIR.mkdir(parents=True, exist_ok=True)
