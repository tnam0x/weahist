from datetime import date

import pandas as pd

from weahist.models import HistoryQuery, Location
from weahist.storage.parquet_cache import ParquetCache


def test_parquet_cache_roundtrip(settings) -> None:
    cache = ParquetCache(settings)
    loc = Location(name="X", latitude=1.0, longitude=2.0, timezone="UTC")
    query = HistoryQuery(location=loc, start=date(2025, 1, 1), end=date(2025, 1, 2))
    df = pd.DataFrame(
        {"temperature_2m": [10.0, 11.0]},
        index=pd.to_datetime(
            ["2025-01-01T00:00:00Z", "2025-01-01T01:00:00Z"], utc=True
        ).rename("time"),
    )

    assert cache.get(query) is None
    cache.put(query, df)
    loaded = cache.get(query)
    assert loaded is not None
    assert len(loaded) == 2
    assert loaded["temperature_2m"].tolist() == [10.0, 11.0]
