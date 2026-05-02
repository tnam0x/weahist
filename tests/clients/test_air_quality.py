from datetime import date

import httpx
import respx

from weahist.clients.air_quality import AirQualityClient
from weahist.clients.base import HttpClient
from weahist.models import Location


def _loc() -> Location:
    return Location(name="Hanoi", latitude=21.03, longitude=105.85, timezone="UTC")


@respx.mock
def test_aqi_returns_dataframe(settings) -> None:
    respx.get(settings.air_quality_url).mock(
        return_value=httpx.Response(
            200,
            json={
                "hourly": {
                    "time": ["2025-04-01T00:00", "2025-04-01T01:00"],
                    "us_aqi": [120, 130],
                    "pm2_5": [50.0, 55.0],
                    "pm10": [80.0, 90.0],
                }
            },
        )
    )
    with HttpClient(settings) as http:
        df = AirQualityClient(http, settings).fetch(
            _loc(), date(2025, 4, 1), date(2025, 4, 1), "hourly"
        )
    assert "us_aqi" in df.columns
    assert len(df) == 2


@respx.mock
def test_aqi_missing_returns_empty(settings) -> None:
    respx.get(settings.air_quality_url).mock(
        return_value=httpx.Response(200, json={"hourly": {"time": []}})
    )
    with HttpClient(settings) as http:
        df = AirQualityClient(http, settings).fetch(
            _loc(), date(2020, 1, 1), date(2020, 1, 2), "hourly"
        )
    assert df.empty
    assert "us_aqi" in df.columns


@respx.mock
def test_aqi_upstream_error_returns_empty(settings) -> None:
    respx.get(settings.air_quality_url).mock(return_value=httpx.Response(500, text="boom"))
    with HttpClient(settings) as http:
        df = AirQualityClient(http, settings).fetch(
            _loc(), date(2020, 1, 1), date(2020, 1, 2), "hourly"
        )
    assert df.empty
