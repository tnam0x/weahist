"""Filter row: range chips, custom dates, my location, recent places, units."""

from __future__ import annotations

import json
from collections.abc import Callable

import pytest
from playwright.sync_api import expect

from tests.e2e.conftest import PREFS_KEY, App

# ---- Range chips ------------------------------------------------------------


def _checked_range(app: App) -> list[str]:
    return app.page.eval_on_selector_all(
        '#range-chips [aria-checked="true"]', "els => els.map(e => e.dataset.range)"
    )


def test_range_chips_select_with_mouse_and_arrow_keys(app: App) -> None:
    app.open()
    page = app.page
    assert _checked_range(app) == ["1w"]

    page.locator('[data-range="3d"]').click()
    expect(page.locator("#kpis")).to_contain_text("72 hourly readings")
    assert _checked_range(app) == ["3d"]
    assert app.prefs()["range"] == "3d"  # type: ignore[index]

    page.keyboard.press("ArrowRight")
    expect(page.locator('[data-range="1w"]')).to_be_focused()
    expect(page.locator("#kpis")).to_contain_text("168 hourly readings")
    assert _checked_range(app) == ["1w"]

    # Roving tabindex: only the checked chip is in the tab order.
    tabbable = page.eval_on_selector_all(
        "#range-chips .chip", "els => els.filter(e => e.tabIndex === 0).map(e => e.dataset.range)"
    )
    assert tabbable == ["1w"]


# ---- Custom range -------------------------------------------------------------


def test_custom_range_loads_the_chosen_dates(app: App) -> None:
    app.open()
    page = app.page
    page.locator("#custom-toggle").click()
    expect(page.locator("#custom-range")).to_be_visible()
    expect(page.locator("#custom-start")).to_be_focused()

    page.locator("#custom-start").fill("2026-03-01")
    page.locator("#custom-end").fill("2026-03-05")
    page.get_by_role("button", name="Apply").click()

    expect(page.locator("#range-subtitle")).to_have_text(
        "Mar 1, 2026 – Mar 5, 2026 · Hourly · Asia/Bangkok"
    )
    expect(page.locator("#custom-range")).to_be_hidden()
    expect(page.locator("#custom-toggle")).to_have_attribute("aria-pressed", "true")
    assert _checked_range(app) == []
    assert app.kpis()["coverage"]["sub"] == f"{5 * 24} hourly readings"
    prefs = app.prefs() or {}
    assert (prefs["range"], prefs["start"], prefs["end"]) == ("custom", "2026-03-01", "2026-03-05")

    # Picking a preset again leaves custom mode.
    page.locator('[data-range="1w"]').click()
    expect(page.locator("#custom-toggle")).to_have_attribute("aria-pressed", "false")
    assert "start" not in (app.prefs() or {})


def test_long_custom_range_is_daily(app: App) -> None:
    app.open("?start=2025-06-01&end=2025-08-31")
    expect(app.page.locator("#range-subtitle")).to_have_text(
        "Jun 1, 2025 – Aug 31, 2025 · Daily · Asia/Bangkok"
    )
    assert app.kpis()["coverage"]["sub"] == "92 daily readings"


@pytest.mark.parametrize(
    ("start", "end", "error"),
    [
        ("2026-03-10", "2026-03-01", "The start date must be on or before the end date."),
        ("2026-03-10", "2026-03-20", "The end date can't be in the future."),
        ("2024-01-01", "2026-03-01", "Pick at most 366 days."),
        ("", "2026-03-01", "Pick both a start and an end date."),
    ],
)
def test_invalid_custom_range_shows_inline_error(
    app: App, start: str, end: str, error: str
) -> None:
    app.open()
    page = app.page
    calls = len(app.mock.requests)
    page.locator("#custom-toggle").click()
    page.locator("#custom-start").fill(start)
    page.locator("#custom-end").fill(end)
    page.get_by_role("button", name="Apply").click()
    expect(page.locator("#custom-error")).to_have_text(error)
    expect(page.locator("#custom-range")).to_be_visible()
    assert len(app.mock.requests) == calls, "an invalid range must not trigger a fetch"

    page.keyboard.press("Escape")
    expect(page.locator("#custom-range")).to_be_hidden()


def test_unusable_shared_range_falls_back_to_default(app: App) -> None:
    app.open("?start=2026-03-10&end=2026-03-01&range=bogus")
    assert _checked_range(app) == ["1w"]
    assert app.kpis()["coverage"]["sub"] == "168 hourly readings"


# ---- My location --------------------------------------------------------------


def test_my_location_uses_device_position(make_app: Callable[..., App]) -> None:
    app = make_app(
        permissions=["geolocation"], geolocation={"latitude": 35.6895, "longitude": 139.6917}
    ).open()
    page = app.page
    page.locator("#locate").click()

    expect(page.locator("#place-title")).to_have_text("My location")
    expect(page.locator("#location-input")).to_have_value("My location (35.69, 139.69)")
    expect(page.locator("#kpis")).to_contain_text("12.0 °C")  # the mock's Tokyo data
    forecast = app.mock.calls("forecast")[-1]
    assert forecast["latitude"] == "35.6895"
    # The browser's zone (Chromium may report the tzdb alias).
    assert forecast["timezone"] in {"Asia/Ho_Chi_Minh", "Asia/Saigon"}

    # Survives a reload without geocoding "My location (…)".
    geocodes = len(app.mock.calls("geocoding"))
    page.reload()
    app.wait_for_chart()
    expect(page.locator("#place-title")).to_have_text("My location")
    assert len(app.mock.calls("geocoding")) == geocodes


def test_my_location_denied_shows_error(make_app: Callable[..., App]) -> None:
    app = make_app(permissions=[]).open()
    app.page.locator("#locate").click()
    expect(app.page.locator("#error-banner")).to_contain_text(
        "Couldn't use your location: permission was denied."
    )


# ---- Recent places ---------------------------------------------------------------


def test_recent_places_are_offered_on_focus(app: App) -> None:
    app.open()
    page = app.page
    loc = page.locator("#location-input")
    loc.fill("Lon")
    page.locator("#location-suggestions li[role=option]", has_text="London").click()
    expect(page.locator("#place-title")).to_have_text("London, United Kingdom")

    page.locator("#page-intro").click()
    loc.focus()
    suggestions = page.locator("#location-suggestions")
    expect(suggestions.locator(".suggestions-head")).to_have_text("Recent")
    expect(suggestions.locator("li[role=option]")).to_have_text(
        ["London, United Kingdom", "Hanoi, Vietnam"]
    )

    geocodes = len(app.mock.calls("geocoding"))
    suggestions.locator("li[role=option]", has_text="Hanoi").click()
    expect(page.locator("#place-title")).to_have_text("Hanoi, Vietnam")
    assert len(app.mock.calls("geocoding")) == geocodes, "recent places are already resolved"


def test_recent_places_are_capped_and_deduplicated(app: App) -> None:
    recent = [
        {
            "label": f"Place {i}",
            "name": f"Place {i}",
            "country": "X",
            "latitude": 0,
            "longitude": 0,
            "timezone": "UTC",
        }
        for i in range(5)
    ]
    app.page.add_init_script(
        f"localStorage.setItem('{PREFS_KEY}', {json.dumps(json.dumps({'recent': recent}))})"
    )
    app.open()
    labels = [r["label"] for r in (app.prefs() or {})["recent"]]
    assert labels == ["Hanoi, Vietnam", "Place 0", "Place 1", "Place 2", "Place 3"]


# ---- Units ---------------------------------------------------------------------------


def test_fahrenheit_converts_kpis_charts_and_tables(app: App) -> None:
    app.open()
    page = app.page
    requests = len(app.mock.requests)
    page.locator('[data-units="f"]').click()

    expect(page.locator('[data-units="f"]')).to_have_attribute("aria-checked", "true")
    expect(page.locator('[data-kpi="temperature"] .kpi-value')).to_have_text("77.0 °F")
    expect(page.locator('[data-kpi="temperature"] .kpi-sub')).to_have_text(
        "Low 68.0 · High 86.0 °F"
    )
    expect(page.locator('[data-kpi="humidity"] .kpi-value')).to_have_text("70%")
    expect(page.locator('[data-chart="temperature"] .card-sub')).to_have_text("°F · hourly")
    expect(page.locator("#chart-temperature .annotation").first).to_have_text("max 86.0 °F")

    card = page.locator('[data-chart="temperature"]')
    card.locator('[data-action="table"]').click()
    expect(card.locator("thead th")).to_have_text(["Time", "Temperature (°F)"])
    expect(card.locator("tbody tr").first.locator("td").last).to_have_text("77.0")

    assert len(app.mock.requests) == requests, "unit changes re-render without refetching"
    assert (app.prefs() or {})["units"] == "f"


def test_units_from_shared_url(app: App) -> None:
    app.open("?units=f")
    expect(app.page.locator('[data-kpi="temperature"] .kpi-value')).to_have_text("77.0 °F")
