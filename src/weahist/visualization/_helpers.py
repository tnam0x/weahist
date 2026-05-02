"""Shared helpers for visualization renderers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from weahist.models import Granularity, Location


@dataclass(frozen=True)
class AqiBand:
    """A US AQI severity band (lower bound inclusive, upper bound inclusive)."""

    lower: int
    upper: int
    label: str
    color: str  # hex


# US EPA AQI bands (https://www.airnow.gov/aqi/aqi-basics/)
AQI_BANDS: tuple[AqiBand, ...] = (
    AqiBand(0, 50, "Good", "#00E400"),
    AqiBand(51, 100, "Moderate", "#FFFF00"),
    AqiBand(101, 150, "Unhealthy for Sensitive Groups", "#FF7E00"),
    AqiBand(151, 200, "Unhealthy", "#FF0000"),
    AqiBand(201, 300, "Very Unhealthy", "#8F3F97"),
    AqiBand(301, 500, "Hazardous", "#7E0023"),
)


def to_local(df: pd.DataFrame, timezone: str) -> pd.DataFrame:
    """Return a copy of `df` whose UTC datetime index is converted to `timezone`."""
    if df.empty or not isinstance(df.index, pd.DatetimeIndex):
        return df
    out = df.copy()
    idx: pd.DatetimeIndex = out.index  # type: ignore[assignment]
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    out.index = idx.tz_convert(timezone)
    return out


def temp_column(df: pd.DataFrame) -> str | None:
    for col in ("temperature_2m", "temperature_2m_mean"):
        if col in df.columns:
            return col
    return None


def aqi_max(df: pd.DataFrame) -> float:
    """Return a sensible upper bound for the AQI y-axis."""
    if "us_aqi" not in df.columns or df["us_aqi"].dropna().empty:
        return 100.0
    observed = float(df["us_aqi"].max())
    # Round up to the next band ceiling so the worst category is fully visible.
    for band in AQI_BANDS:
        if observed <= band.upper:
            return float(band.upper)
    return 500.0


def build_title(
    location: Location,
    start: date,
    end: date,
    granularity: Granularity,
    rows: int,
) -> tuple[str, str]:
    """Return `(title, subtitle)` strings for chart headers."""
    place = location.name + (f", {location.country}" if location.country else "")
    title = f"Weather & Air Quality — {place}"
    subtitle = (
        f"{start:%b %-d} → {end:%b %-d, %Y} · {granularity.capitalize()} · source: Open-Meteo"
    )
    return title, subtitle


def aqi_category(value: float) -> str:
    """Return the US AQI category label for `value` (clamped to 0..500)."""
    for band in AQI_BANDS:
        if value <= band.upper:
            return band.label
    return AQI_BANDS[-1].label


def day_boundaries(index: pd.DatetimeIndex) -> list[pd.Timestamp]:
    """Return midnight timestamps (in `index`'s tz) covered by the range."""
    if len(index) == 0:
        return []
    start = index.min().normalize()
    end = index.max().normalize() + pd.Timedelta(days=1)
    return list(pd.date_range(start=start, end=end, freq="1D", tz=index.tz))


def weekend_spans(index: pd.DatetimeIndex) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Return list of `(start, end)` timestamps covering Saturday+Sunday in range."""
    spans: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    for midnight in day_boundaries(index):
        if midnight.dayofweek == 5:  # Saturday
            spans.append((midnight, midnight + pd.Timedelta(days=2)))
    return spans
