from datetime import date

import pandas as pd
import pytest

from weahist.models import HistoryQuery, Location
from weahist.services.history import WeatherHistoryService


class _FakeCache:
    def __init__(self) -> None:
        self.store: dict[tuple, pd.DataFrame] = {}

    def _key(self, q: HistoryQuery) -> tuple:
        return (q.location.latitude, q.location.longitude, q.start, q.end, q.granularity)

    def get(self, query: HistoryQuery) -> pd.DataFrame | None:
        return self.store.get(self._key(query))

    def put(self, query: HistoryQuery, df: pd.DataFrame) -> None:
        self.store[self._key(query)] = df


class _FakeGeocoder:
    def geocode(self, name: str) -> Location:
        return Location(name=name, latitude=21.03, longitude=105.85, timezone="UTC")


class _FakeArchive:
    def fetch(self, loc, start, end, gran) -> pd.DataFrame:
        idx = pd.to_datetime(
            ["2025-04-01T00:00Z", "2025-04-01T01:00Z"], utc=True
        ).rename("time")
        return pd.DataFrame(
            {"temperature_2m": [22.0, 21.5], "relative_humidity_2m": [80, 82]},
            index=idx,
        )


class _FakeAQI:
    def __init__(self, empty: bool = False) -> None:
        self.empty = empty

    def fetch(self, loc, start, end, gran) -> pd.DataFrame:
        if self.empty:
            return pd.DataFrame(columns=["us_aqi", "pm2_5", "pm10"]).rename_axis("time")
        idx = pd.to_datetime(
            ["2025-04-01T00:00Z", "2025-04-01T01:00Z"], utc=True
        ).rename("time")
        return pd.DataFrame(
            {"us_aqi": [120, 130], "pm2_5": [50.0, 55.0], "pm10": [80.0, 90.0]},
            index=idx,
        )


@pytest.fixture()
def service(settings):
    return WeatherHistoryService(
        settings=settings,
        cache=_FakeCache(),
        geocoder=_FakeGeocoder(),
        archive=_FakeArchive(),
        air_quality=_FakeAQI(),
    )


def test_get_history_merges_weather_and_aqi(service) -> None:
    query, df = service.get_history("Hanoi", date(2025, 4, 1), date(2025, 4, 1), "hourly")
    assert query.location.name == "Hanoi"
    assert {"temperature_2m", "relative_humidity_2m", "us_aqi"}.issubset(df.columns)
    assert len(df) == 2


def test_get_history_without_aqi_returns_weather_only(settings) -> None:
    svc = WeatherHistoryService(
        settings=settings,
        cache=_FakeCache(),
        geocoder=_FakeGeocoder(),
        archive=_FakeArchive(),
        air_quality=_FakeAQI(empty=True),
    )
    _, df = svc.get_history("Hanoi", date(2025, 4, 1), date(2025, 4, 1), "hourly")
    assert "temperature_2m" in df.columns
    assert "us_aqi" not in df.columns


def test_cache_hit_skips_clients(settings) -> None:
    cache = _FakeCache()
    svc = WeatherHistoryService(
        settings=settings,
        cache=cache,
        geocoder=_FakeGeocoder(),
        archive=_FakeArchive(),
        air_quality=_FakeAQI(),
    )
    q1, df1 = svc.get_history("Hanoi", date(2025, 4, 1), date(2025, 4, 1), "hourly")
    # Replace clients with ones that would explode if called
    class _Boom:
        def fetch(self, *a, **k): raise AssertionError("should not be called")
    svc._archive = _Boom()  # type: ignore[assignment]
    svc._air_quality = _Boom()  # type: ignore[assignment]
    q2, df2 = svc.get_history("Hanoi", date(2025, 4, 1), date(2025, 4, 1), "hourly")
    assert q1 == q2
    assert df1.equals(df2)
