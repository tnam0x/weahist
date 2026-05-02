"""Open-Meteo air-quality client.

AQI history may be shallower than the requested range. We return an empty
DataFrame (with expected columns) and log a warning rather than raising.
"""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd

from weahist.clients.base import HttpClient
from weahist.config import Settings
from weahist.errors import UpstreamError
from weahist.models import Granularity, Location

logger = logging.getLogger(__name__)

_HOURLY_VARS = ["us_aqi", "pm2_5", "pm10"]


class AirQualityClient:
    def __init__(self, http: HttpClient, settings: Settings) -> None:
        self._http = http
        self._settings = settings

    def fetch(
        self,
        location: Location,
        start: date,
        end: date,
        granularity: Granularity,
    ) -> pd.DataFrame:
        """Return a UTC-indexed DataFrame of AQI values; possibly empty.

        For `granularity="daily"`, hourly data is fetched and resampled to daily means.
        Returns an empty frame (same columns) if the upstream has no coverage.
        """
        empty = pd.DataFrame(columns=_HOURLY_VARS).rename_axis("time")
        params: dict[str, object] = {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "timezone": "UTC",
            "hourly": ",".join(_HOURLY_VARS),
        }

        try:
            data = self._http.get_json(self._settings.air_quality_url, params)
        except UpstreamError as exc:
            logger.warning("air-quality fetch failed; continuing without AQI: %s", exc)
            return empty

        block = data.get("hourly")
        if not isinstance(block, dict) or "time" not in block or not block["time"]:
            logger.warning(
                "air-quality history unavailable for %s..%s at (%.3f, %.3f)",
                start,
                end,
                location.latitude,
                location.longitude,
            )
            return empty

        times = pd.to_datetime(block["time"], utc=True)
        df = pd.DataFrame({"time": times})
        for var in _HOURLY_VARS:
            df[var] = block.get(var)
        df = df.set_index("time").sort_index()

        # Drop rows where every AQI value is missing.
        df = df.dropna(how="all")
        if df.empty:
            logger.warning("air-quality response contained no usable rows")
            return empty

        if granularity == "daily":
            df = df.resample("1D").mean(numeric_only=True)
        return df
