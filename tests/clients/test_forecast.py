from datetime import date

import httpx
import respx

from weahist.clients.base import HttpClient
from weahist.clients.forecast import ForecastClient
from weahist.models import Location


def _loc() -> Location:
    return Location(name="Hanoi", latitude=21.03, longitude=105.85, timezone="UTC")


@respx.mock
def test_forecast_hourly_returns_indexed_df(settings) -> None:
    respx.get(settings.forecast_url).mock(
        return_value=httpx.Response(
            200,
            json={
                "hourly": {
                    "time": ["2025-04-10T00:00", "2025-04-10T01:00"],
                    "temperature_2m": [25.0, 24.5],
                    "relative_humidity_2m": [70, 72],
                }
            },
        )
    )
    with HttpClient(settings) as http:
        df = ForecastClient(http, settings).fetch(
            _loc(), date(2025, 4, 10), date(2025, 4, 10), "hourly"
        )
    assert list(df.columns) == ["temperature_2m", "relative_humidity_2m"]
    assert len(df) == 2
    assert df.index.tz is not None
