"""Deterministic in-browser mock of the Open-Meteo HTTP APIs.

Installed on a Playwright page via ``page.route`` so the frontend in ``web/``
runs hermetically. Responses are synthesised from the request's query params
(``start_date``/``end_date``/``hourly``/``daily``), so any range the app asks
for gets a well-formed, predictable payload.

Synthetic values (hourly):
- temperature = base + 5·sin(2πh/24)  → max base+5, min base-5
- humidity    = 70 - 10·sin(2πh/24)   (anti-correlated with temperature, as in reality)
- US AQI      = 40 + 30·sin(2πh/24)   → max 70, min 10, daily mean 40
"""

from __future__ import annotations

import contextlib
import json
import math
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import Page, Route

OPEN_METEO_PATTERN = re.compile(r"^https://[a-z-]+\.open-meteo\.com/")


@dataclass(frozen=True)
class Place:
    name: str
    country: str
    admin1: str | None
    latitude: float
    longitude: float
    timezone: str
    base_temp: float

    @property
    def label(self) -> str:
        return ", ".join(p for p in (self.name, self.admin1, self.country) if p)

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "country": self.country,
            "admin1": self.admin1,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "timezone": self.timezone,
        }


HANOI = Place("Hanoi", "Vietnam", None, 21.0245, 105.8412, "Asia/Bangkok", 25.0)
LONDON = Place("London", "United Kingdom", "England", 51.5085, -0.1257, "Europe/London", 10.0)
LONGYEARBYEN = Place(
    "Longyearbyen", "Svalbard and Jan Mayen", None, 78.2232, 15.6267, "Arctic/Longyearbyen", -10.0
)
TOKYO = Place("Tokyo", "Japan", "Tokyo", 35.6895, 139.6917, "Asia/Tokyo", 12.0)
DEFAULT_PLACES = (HANOI, LONDON, LONGYEARBYEN, TOKYO)


def _dates(start: str, end: str) -> list[date]:
    d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
    return [d0 + timedelta(days=i) for i in range((d1 - d0).days + 1)]


def _wave(h: int) -> float:
    return math.sin(2 * math.pi * h / 24)


@dataclass
class OpenMeteoMock:
    places: tuple[Place, ...] = DEFAULT_PLACES
    # Per-endpoint HTTP status overrides, keyed by "geocoding" | "archive" |
    # "forecast" | "air-quality".
    fail: dict[str, int] = field(default_factory=dict)
    # When True, requests are parked in `held` instead of being answered.
    hold: bool = False
    held: list[Route] = field(default_factory=list)
    requests: list[tuple[str, dict[str, str]]] = field(default_factory=list)
    # -1.0: humidity peaks when temperature bottoms out (realistic);
    # +1.0: both peak at the same hour (worst case for label placement).
    humidity_phase: float = -1.0

    def install(self, page: Page) -> None:
        page.route(OPEN_METEO_PATTERN, self._handle)

    def release(self) -> None:
        """Answer every held request (used after asserting a loading state)."""
        self.hold = False
        held, self.held = self.held, []
        for route in held:
            self._handle(route)

    def abort_held(self) -> None:
        """Drop still-parked requests so teardown doesn't leave pending tasks."""
        held, self.held = self.held, []
        for route in held:
            with contextlib.suppress(Exception):  # page/context already closed
                route.abort()

    def calls(self, endpoint: str) -> list[dict[str, str]]:
        return [params for ep, params in self.requests if ep == endpoint]

    # ---- routing -----------------------------------------------------
    def _handle(self, route: Route) -> None:
        url = urlparse(route.request.url)
        params = {k: v[0] for k, v in parse_qs(url.query).items()}
        endpoint = self._endpoint(url.hostname or "", url.path)
        self.requests.append((endpoint, params))

        if self.hold:
            self.held.append(route)
            return
        if endpoint in self.fail:
            route.fulfill(
                status=self.fail[endpoint],
                content_type="application/json",
                body=json.dumps({"error": True, "reason": f"mock {endpoint} failure"}),
                headers={"Access-Control-Allow-Origin": "*"},
            )
            return

        body = {
            "geocoding": self._geocoding,
            "archive": self._weather,
            "forecast": self._weather,
            "air-quality": self._air_quality,
        }[endpoint](params)
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(body),
            headers={"Access-Control-Allow-Origin": "*"},
        )

    @staticmethod
    def _endpoint(host: str, path: str) -> str:
        if host.startswith("geocoding-api"):
            return "geocoding"
        if host.startswith("archive-api"):
            return "archive"
        if host.startswith("air-quality-api"):
            return "air-quality"
        if path.endswith("/forecast"):
            return "forecast"
        raise AssertionError(f"unexpected Open-Meteo URL: {host}{path}")

    # ---- payloads ----------------------------------------------------
    def _place_at(self, params: dict[str, str]) -> Place:
        lat = float(params["latitude"])
        return min(self.places, key=lambda p: abs(p.latitude - lat))

    def _geocoding(self, params: dict[str, str]) -> dict[str, Any]:
        q = params.get("name", "").strip().lower()
        count = int(params.get("count", "10"))
        hits = [p.to_json() for p in self.places if p.name.lower().startswith(q)][:count]
        # Real API omits `results` entirely when nothing matches.
        return {"results": hits} if hits else {"generationtime_ms": 0.1}

    def _weather(self, params: dict[str, str]) -> dict[str, Any]:
        place = self._place_at(params)
        days = _dates(params["start_date"], params["end_date"])
        if "hourly" in params:
            times, temp, humid = [], [], []
            for d in days:
                for h in range(24):
                    times.append(f"{d.isoformat()}T{h:02d}:00")
                    temp.append(round(place.base_temp + 5 * _wave(h), 2))
                    humid.append(round(70 + self.humidity_phase * 10 * _wave(h), 2))
            return {
                "timezone": place.timezone,
                "hourly": {
                    "time": times,
                    "temperature_2m": temp,
                    "relative_humidity_2m": humid,
                },
            }
        mean = [round(place.base_temp + 3 * math.sin(d.toordinal()), 2) for d in days]
        return {
            "timezone": place.timezone,
            "daily": {
                "time": [d.isoformat() for d in days],
                "temperature_2m_max": [m + 5 for m in mean],
                "temperature_2m_min": [m - 5 for m in mean],
                "temperature_2m_mean": mean,
            },
        }

    def _air_quality(self, params: dict[str, str]) -> dict[str, Any]:
        times, aqi, pm25, pm10 = [], [], [], []
        for d in _dates(params["start_date"], params["end_date"]):
            for h in range(24):
                times.append(f"{d.isoformat()}T{h:02d}:00")
                aqi.append(round(40 + 30 * _wave(h)))
                pm25.append(12.0)
                pm10.append(20.0)
        return {
            "hourly": {"time": times, "us_aqi": aqi, "pm2_5": pm25, "pm10": pm10},
        }
