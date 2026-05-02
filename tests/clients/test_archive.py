from datetime import date

import httpx
import respx

from weahist.clients.archive import ArchiveClient
from weahist.clients.base import HttpClient
from weahist.models import Location


def _loc() -> Location:
    return Location(name="Hanoi", latitude=21.03, longitude=105.85, timezone="UTC")


@respx.mock
def test_archive_hourly_returns_indexed_df(settings) -> None:
    respx.get(settings.archive_url).mock(
        return_value=httpx.Response(
            200,
            json={
                "hourly": {
                    "time": ["2025-04-01T00:00", "2025-04-01T01:00"],
                    "temperature_2m": [22.1, 21.8],
                    "relative_humidity_2m": [80, 82],
                }
            },
        )
    )
    with HttpClient(settings) as http:
        df = ArchiveClient(http, settings).fetch(
            _loc(), date(2025, 4, 1), date(2025, 4, 1), "hourly"
        )
    assert list(df.columns) == ["temperature_2m", "relative_humidity_2m"]
    assert len(df) == 2
    assert df.index.tz is not None
