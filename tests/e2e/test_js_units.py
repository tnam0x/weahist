"""Unit tests for the pure ES modules in ``web/``, run inside the browser.

The modules are imported with dynamic ``import()`` on a blank page served from
the same origin, so no app bootstrapping or network mocking is involved.
"""

from __future__ import annotations

from typing import Any

import pytest
from playwright.sync_api import Page

from tests.e2e.conftest import FIXED_NOW


@pytest.fixture()
def js(page: Page) -> Page:
    page.clock.install(time=FIXED_NOW)
    page.route(
        "**/*",
        lambda route: route.abort() if "open-meteo" in route.request.url else route.continue_(),
    )
    page.goto("/aqi.js")  # any same-origin URL works as a module base
    return page


def call(page: Page, module: str, expr: str, arg: Any = None) -> Any:
    return page.evaluate(
        f"async (arg) => {{ const m = await import('/{module}'); return {expr}; }}", arg
    )


# ---- aqi.js -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "category"),
    [
        (0, "Good"),
        (50, "Good"),
        (51, "Moderate"),
        (100, "Moderate"),
        (101, "Unhealthy for Sensitive Groups"),
        (150, "Unhealthy for Sensitive Groups"),
        (151, "Unhealthy"),
        (200, "Unhealthy"),
        (201, "Very Unhealthy"),
        (300, "Very Unhealthy"),
        (301, "Hazardous"),
        (500, "Hazardous"),
        (999, "Hazardous"),
    ],
)
def test_aqi_category_band_edges(js: Page, value: int, category: str) -> None:
    assert call(js, "aqi.js", "m.aqiCategory(arg)", value) == category


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([], 100),
        ([None, None], 100),
        ([10, 42], 50),
        ([10, None, 75], 100),
        ([180], 200),
        ([450], 500),
        ([800], 500),
    ],
)
def test_aqi_axis_max_is_ceiling_of_worst_band(js: Page, values: list[Any], expected: int) -> None:
    assert call(js, "aqi.js", "m.aqiMax(arg)", values) == expected


def test_aqi_bands_are_contiguous(js: Page) -> None:
    bands = call(js, "aqi.js", "m.AQI_BANDS")
    assert bands[0]["lower"] == 0
    assert bands[-1]["upper"] == 500
    for prev, nxt in zip(bands, bands[1:], strict=False):
        assert nxt["lower"] == prev["upper"] + 1


# ---- api.js -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("key", "start", "granularity"),
    [
        ("1d", "2026-03-15", "hourly"),
        ("3d", "2026-03-13", "hourly"),
        ("1w", "2026-03-09", "hourly"),
        ("2w", "2026-03-02", "hourly"),
        ("1m", "2026-02-14", "hourly"),
        ("3m", "2025-12-16", "daily"),
        ("6m", "2025-09-17", "daily"),
        ("1y", "2025-03-16", "daily"),
        ("bogus", "2026-03-09", "hourly"),  # unknown keys fall back to 1w
    ],
)
def test_resolve_range(js: Page, key: str, start: str, granularity: str) -> None:
    assert call(js, "api.js", "m.resolveRange(arg)", key) == {
        "start": start,
        "end": "2026-03-15",
        "granularity": granularity,
    }


def test_geocode_ignores_blank_query_without_network(js: Page) -> None:
    assert call(js, "api.js", "m.geocode('   ')") == []


# ---- theme.js ---------------------------------------------------------------


def test_palette_for_theme(js: Page) -> None:
    assert call(js, "theme.js", "m.paletteFor('dark').paperBg") == "#161B22"
    assert call(js, "theme.js", "m.paletteFor('light').paperBg") == "#FFFFFF"
    assert call(js, "theme.js", "m.paletteFor('unknown').paperBg") == "#FFFFFF"
