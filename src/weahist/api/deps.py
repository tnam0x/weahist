"""FastAPI service dependencies."""

from __future__ import annotations

from functools import lru_cache

from weahist.services.history import WeatherHistoryService


@lru_cache(maxsize=1)
def get_service() -> WeatherHistoryService:
    return WeatherHistoryService()
