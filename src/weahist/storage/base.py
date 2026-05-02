"""Cache backend protocol."""

from __future__ import annotations

from typing import Protocol

import pandas as pd

from weahist.models import HistoryQuery


class CacheBackend(Protocol):
    """Storage seam for cached history results."""

    def get(self, query: HistoryQuery) -> pd.DataFrame | None:
        """Return cached frame or `None` if missing/stale."""

    def put(self, query: HistoryQuery, df: pd.DataFrame) -> None:
        """Persist `df` for `query`."""
