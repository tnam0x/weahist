"""Weather history service — orchestrates geocoding, fetch, merge, cache."""

from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd

from weahist.clients.air_quality import AirQualityClient
from weahist.clients.archive import ArchiveClient
from weahist.clients.base import HttpClient
from weahist.clients.forecast import ForecastClient
from weahist.clients.geocoding import GeocodingClient
from weahist.config import Settings, get_settings
from weahist.errors import InvalidRangeError
from weahist.models import Granularity, HistoryQuery, Location
from weahist.storage.base import CacheBackend
from weahist.storage.parquet_cache import ParquetCache

logger = logging.getLogger(__name__)


class WeatherHistoryService:
    """Combines weather + AQI data for a `HistoryQuery`."""

    def __init__(
        self,
        settings: Settings | None = None,
        http: HttpClient | None = None,
        cache: CacheBackend | None = None,
        geocoder: GeocodingClient | None = None,
        archive: ArchiveClient | None = None,
        forecast: ForecastClient | None = None,
        air_quality: AirQualityClient | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._http = http or HttpClient(self._settings)
        self._cache: CacheBackend = cache or ParquetCache(self._settings)
        self._geocoder = geocoder or GeocodingClient(self._http, self._settings)
        self._archive = archive or ArchiveClient(self._http, self._settings)
        self._forecast = forecast or ForecastClient(self._http, self._settings)
        self._air_quality = air_quality or AirQualityClient(self._http, self._settings)

    def resolve_location(self, name: str) -> Location:
        return self._geocoder.geocode(name)

    def get_history(
        self,
        location: Location | str,
        start: date,
        end: date,
        granularity: Granularity = "hourly",
        use_cache: bool = True,
    ) -> tuple[HistoryQuery, pd.DataFrame]:
        """Return `(query, dataframe)` for the requested location/range.

        DataFrame is UTC-indexed; columns include weather variables and (when
        available) AQI variables. AQI columns may be all-NaN if upstream lacks
        coverage — never raises for that case.

        Weather is sourced from the archive endpoint for older days and the
        forecast endpoint for the trailing ``forecast_tail_days`` window
        (default 3) so that "today" is included.

        Raises:
            InvalidRangeError: if ``start > end`` or ``end`` is in the future.
        """
        today = date.today()
        if start > end:
            raise InvalidRangeError(f"start {start} is after end {end}")
        if end > today:
            raise InvalidRangeError(f"end {end} is in the future (today is {today})")

        loc = location if isinstance(location, Location) else self.resolve_location(location)
        query = HistoryQuery(location=loc, start=start, end=end, granularity=granularity)

        if use_cache:
            cached = self._cache.get(query)
            if cached is not None:
                logger.info("cache hit for %s..%s @ %s", start, end, loc.name)
                return query, cached

        weather_df = self._fetch_weather(loc, start, end, granularity, today)
        aqi_df = self._air_quality.fetch(loc, start, end, granularity)

        merged = weather_df.join(aqi_df, how="left") if not aqi_df.empty else weather_df.copy()
        if aqi_df.empty:
            logger.warning(
                "AQI history unavailable for %s; returning weather-only frame", loc.name
            )

        if use_cache:
            self._cache.put(query, merged)
        return query, merged

    def _fetch_weather(
        self,
        loc: Location,
        start: date,
        end: date,
        granularity: Granularity,
        today: date,
    ) -> pd.DataFrame:
        """Hybrid archive + forecast fetch.

        Older days come from the archive (final reanalysis); the trailing
        ``forecast_tail_days`` window comes from the forecast endpoint
        (live observations + model output).
        """
        tail = self._settings.forecast_tail_days
        forecast_start = today - timedelta(days=tail)
        archive_end = forecast_start - timedelta(days=1)

        frames: list[pd.DataFrame] = []
        if start <= archive_end:
            a_end = min(end, archive_end)
            frames.append(self._archive.fetch(loc, start, a_end, granularity))
        if end >= forecast_start:
            f_start = max(start, forecast_start)
            f_end = min(end, today)
            frames.append(self._forecast.fetch(loc, f_start, f_end, granularity))

        if not frames:
            # Defensive: validation should make this unreachable.
            return pd.DataFrame().rename_axis("time")

        if len(frames) == 1:
            return frames[0]

        # Concatenate, then resolve duplicate timestamps (prefer archive,
        # which is `frames[0]`, since it appears first under `keep="first"`).
        combined = pd.concat(frames)
        combined = combined[~combined.index.duplicated(keep="first")]
        return combined.sort_index()
