"""Renderer Protocol."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

import pandas as pd

from weahist.models import HistoryQuery


class Renderer(Protocol):
    """Render a history DataFrame to a file."""

    extension: str

    def render(self, df: pd.DataFrame, query: HistoryQuery, output: Path) -> Path:
        """Write a chart for `df` to `output` and return the path."""
