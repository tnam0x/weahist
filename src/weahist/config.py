"""Application configuration via pydantic-settings."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from env vars and `.env`."""

    model_config = SettingsConfigDict(
        env_prefix="WEAHIST_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    cache_dir: Path = Field(default=Path(".cache/weahist"))
    cache_ttl_hours: int = Field(default=24, ge=0)
    http_timeout_seconds: float = Field(default=15.0, gt=0)
    http_max_retries: int = Field(default=3, ge=0)

    geocoding_url: str = "https://geocoding-api.open-meteo.com/v1/search"
    archive_url: str = "https://archive-api.open-meteo.com/v1/archive"
    forecast_url: str = "https://api.open-meteo.com/v1/forecast"
    air_quality_url: str = "https://air-quality-api.open-meteo.com/v1/air-quality"

    # The archive endpoint typically lags real time by 1–3 days. For dates
    # inside this trailing window (today − N … today) we use the forecast
    # endpoint instead, which has live observations + model output.
    forecast_tail_days: int = Field(default=3, ge=0)


def get_settings() -> Settings:
    """Return a fresh `Settings` instance (cheap; allows env overrides in tests)."""
    return Settings()
