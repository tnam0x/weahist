"""Open-Meteo historical weather (archive) client."""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd

from weahist.clients.base import HttpClient
from weahist.config import Settings
from weahist.errors import UpstreamError
from weahist.models import Granularity, Location

logger = logging.getLogger(__name__)

_HOURLY_VARS = ["temperature_2m", "relative_humidity_2m"]
_DAILY_VARS = [
    "temperature_2m_max",
    "temperature_2m_min",
    "temperature_2m_mean",
]


class ArchiveClient:
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
        """Return a UTC-indexed DataFrame of archived weather observations."""
        params: dict[str, object] = {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "timezone": "UTC",
        }
        if granularity == "hourly":
            params["hourly"] = ",".join(_HOURLY_VARS)
            block_key = "hourly"
        else:
            params["daily"] = ",".join(_DAILY_VARS)
            block_key = "daily"

        data = self._http.get_json(self._settings.archive_url, params)
        block = data.get(block_key)
        if not isinstance(block, dict) or "time" not in block:
            raise UpstreamError(f"archive response missing {block_key!r} block")

        times = pd.to_datetime(block["time"], utc=True)
        df = pd.DataFrame({"time": times})
        for var in _HOURLY_VARS if granularity == "hourly" else _DAILY_VARS:
            if var in block:
                df[var] = block[var]
        return df.set_index("time").sort_index()
