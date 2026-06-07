"""Centralised configuration loaded from environment variables."""
from __future__ import annotations

import logging
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", populate_by_name=True)

    # ── Required API keys ────────────────────────────────────────────────────
    tmdb_api_key: str = Field(..., alias="TMDB_API_KEY")
    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")

    # ── Instagram (Phase 2) ───────────────────────────────────────────────────
    instagram_access_token: str = Field(default="", alias="INSTAGRAM_ACCESS_TOKEN")
    instagram_user_id: str = Field(default="", alias="INSTAGRAM_USER_ID")

    # ── GitHub (auto-injected in Actions) ────────────────────────────────────
    github_token: str = Field(default="", alias="GITHUB_TOKEN")
    github_repository: str = Field(default="", alias="GITHUB_REPOSITORY")

    # ── TMDb ─────────────────────────────────────────────────────────────────
    tmdb_base_url: str = "https://api.themoviedb.org/3"
    tmdb_image_base_url: str = "https://image.tmdb.org/t/p/w500"

    # ── OpenAI ────────────────────────────────────────────────────────────────
    openai_model: str = "gpt-4o-mini"

    # ── Behaviour ─────────────────────────────────────────────────────────────
    days_lookback: int = 1
    max_releases_per_platform: int = 5

    # ── Paths ─────────────────────────────────────────────────────────────────
    drafts_dir: Path = Path("drafts")
    data_dir: Path = Path("data")
    config_dir: Path = Path("config")

    # ── Image ─────────────────────────────────────────────────────────────────
    image_width: int = 1080
    image_height: int = 1080


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
