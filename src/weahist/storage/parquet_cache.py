"""Parquet-backed cache for history queries."""

from __future__ import annotations

import logging
import time
from pathlib import Path

import pandas as pd

from weahist.config import Settings
from weahist.errors import CacheError
from weahist.models import HistoryQuery

logger = logging.getLogger(__name__)


class ParquetCache:
    """Stores each query result as a single Parquet file under `settings.cache_dir`."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._dir = Path(settings.cache_dir)

    def _path(self, query: HistoryQuery) -> Path:
        loc = query.location
        key = (
            f"{loc.latitude:.4f}_{loc.longitude:.4f}"
            f"_{query.start.isoformat()}_{query.end.isoformat()}_{query.granularity}.parquet"
        )
        return self._dir / key

    def _is_fresh(self, path: Path) -> bool:
        ttl = self._settings.cache_ttl_hours
        if ttl <= 0:
            return True
        age_hours = (time.time() - path.stat().st_mtime) / 3600.0
        return age_hours < ttl

    def get(self, query: HistoryQuery) -> pd.DataFrame | None:
        path = self._path(query)
        if not path.exists() or not self._is_fresh(path):
            return None
        try:
            df = pd.read_parquet(path)
        except Exception as exc:  # noqa: BLE001 — surface as CacheError
            raise CacheError(f"failed to read cache {path}: {exc}") from exc
        if "time" in df.columns:
            df = df.set_index("time")
        df.index = pd.to_datetime(df.index, utc=True)
        return df

    def put(self, query: HistoryQuery, df: pd.DataFrame) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._path(query)
        try:
            df.reset_index().to_parquet(path, index=False)
        except Exception as exc:  # noqa: BLE001
            raise CacheError(f"failed to write cache {path}: {exc}") from exc
        logger.debug("cache write: %s (%d rows)", path, len(df))
