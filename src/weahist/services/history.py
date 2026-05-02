"""Weather history service — orchestrates geocoding, fetch, merge, cache."""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd

from weahist.clients.air_quality import AirQualityClient
from weahist.clients.archive import ArchiveClient
from weahist.clients.base import HttpClient
from weahist.clients.geocoding import GeocodingClient
from weahist.config import Settings, get_settings
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
        air_quality: AirQualityClient | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._http = http or HttpClient(self._settings)
        self._cache: CacheBackend = cache or ParquetCache(self._settings)
        self._geocoder = geocoder or GeocodingClient(self._http, self._settings)
        self._archive = archive or ArchiveClient(self._http, self._settings)
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
        """
        loc = location if isinstance(location, Location) else self.resolve_location(location)
        query = HistoryQuery(location=loc, start=start, end=end, granularity=granularity)

        if use_cache:
            cached = self._cache.get(query)
            if cached is not None:
                logger.info("cache hit for %s..%s @ %s", start, end, loc.name)
                return query, cached

        weather_df = self._archive.fetch(loc, start, end, granularity)
        aqi_df = self._air_quality.fetch(loc, start, end, granularity)

        merged = weather_df.join(aqi_df, how="left") if not aqi_df.empty else weather_df.copy()
        if aqi_df.empty:
            logger.warning(
                "AQI history unavailable for %s; returning weather-only frame", loc.name
            )

        if use_cache:
            self._cache.put(query, merged)
        return query, merged
