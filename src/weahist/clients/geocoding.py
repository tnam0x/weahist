"""Open-Meteo geocoding client."""

from __future__ import annotations

import logging

from weahist.clients.base import HttpClient
from weahist.config import Settings
from weahist.errors import GeocodingError
from weahist.models import Location

logger = logging.getLogger(__name__)


class GeocodingClient:
    def __init__(self, http: HttpClient, settings: Settings) -> None:
        self._http = http
        self._settings = settings

    def geocode(self, name: str, count: int = 1) -> Location:
        """Resolve a place name to a `Location` (first match)."""
        if not name.strip():
            raise GeocodingError("location name is empty")

        data = self._http.get_json(
            self._settings.geocoding_url,
            {"name": name, "count": count, "format": "json", "language": "en"},
        )
        results = data.get("results") or []
        if not results:
            raise GeocodingError(f"no geocoding results for {name!r}")

        top = results[0]
        try:
            return Location(
                name=top.get("name", name),
                latitude=float(top["latitude"]),
                longitude=float(top["longitude"]),
                country=top.get("country"),
                timezone=top.get("timezone", "UTC"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise GeocodingError(f"malformed geocoding payload: {exc}") from exc
