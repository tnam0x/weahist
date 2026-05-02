from datetime import date, timedelta

import pandas as pd
import pytest

from weahist.errors import InvalidRangeError
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


def test_invalid_range_rejected(service) -> None:
    with pytest.raises(InvalidRangeError):
        service.get_history("Hanoi", date(2025, 4, 2), date(2025, 4, 1), "hourly")
    future = date.today() + timedelta(days=5)
    with pytest.raises(InvalidRangeError):
        service.get_history("Hanoi", date.today(), future, "hourly")


class _RecordingArchive:
    def __init__(self) -> None:
        self.calls: list[tuple[date, date]] = []

    def fetch(self, loc, start, end, gran) -> pd.DataFrame:
        self.calls.append((start, end))
        idx = pd.to_datetime([f"{start.isoformat()}T00:00Z"], utc=True).rename("time")
        return pd.DataFrame({"temperature_2m": [10.0], "relative_humidity_2m": [50]}, index=idx)


class _RecordingForecast:
    def __init__(self) -> None:
        self.calls: list[tuple[date, date]] = []

    def fetch(self, loc, start, end, gran) -> pd.DataFrame:
        self.calls.append((start, end))
        idx = pd.to_datetime([f"{start.isoformat()}T00:00Z"], utc=True).rename("time")
        return pd.DataFrame({"temperature_2m": [20.0], "relative_humidity_2m": [60]}, index=idx)


def test_hybrid_uses_archive_and_forecast(settings) -> None:
    archive = _RecordingArchive()
    forecast = _RecordingForecast()
    svc = WeatherHistoryService(
        settings=settings,
        cache=_FakeCache(),
        geocoder=_FakeGeocoder(),
        archive=archive,
        forecast=forecast,  # type: ignore[arg-type]
        air_quality=_FakeAQI(empty=True),
    )
    today = date.today()
    start = today - timedelta(days=10)
    _, df = svc.get_history("Hanoi", start, today, "hourly")
    assert len(archive.calls) == 1
    assert len(forecast.calls) == 1
    a_start, a_end = archive.calls[0]
    f_start, f_end = forecast.calls[0]
    assert a_start == start
    assert a_end == today - timedelta(days=settings.forecast_tail_days + 1)
    assert f_start == today - timedelta(days=settings.forecast_tail_days)
    assert f_end == today
    assert not df.empty
