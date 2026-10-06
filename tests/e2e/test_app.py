"""End-to-end behaviour of the static frontend: loading, controls, prefs, errors."""

from __future__ import annotations

import json
from typing import Any

from playwright.sync_api import expect

from tests.e2e.conftest import PREFS_KEY, App
from tests.e2e.openmeteo_mock import Place

# ---- Initial load --------------------------------------------------------


def test_default_view_renders_hanoi_last_7_days(app: App) -> None:
    app.open()
    page = app.page

    expect(page.locator("#location-input")).to_have_value("Hanoi, Vietnam")
    expect(page.locator("#range-select")).to_have_value("1w")
    expect(page.locator("#status")).to_have_text("")
    expect(page.locator("#error-banner")).to_be_hidden()

    assert app.heading() == (
        "Hanoi, Vietnam",
        "Mar 9, 2026 – Mar 15, 2026 · Hourly · Asia/Bangkok",
    )
    assert app.kpis() == {
        "temperature": {
            "label": "Avg temperature",
            "value": "25.0 °C",
            "sub": "Low 20.0 · High 30.0 °C",
        },
        "humidity": {"label": "Avg humidity", "value": "70%", "sub": "Low 60 · High 80%"},
        "aqi": {
            "label": "Peak AQI (US)",
            "value": "70Moderate",
            "sub": "Unusually sensitive people should limit prolonged outdoor exertion.",
        },
        "coverage": {"label": "AQI coverage", "value": "100%", "sub": "168 hourly readings"},
    }
    assert app.traces("temperature") == [{"name": "Value", "n": 168}]
    assert app.traces("humidity") == [{"name": "Value", "n": 168}]
    assert app.traces("aqi") == [{"name": "AQI", "n": 168}]


def test_recent_days_come_from_forecast_and_older_from_archive(app: App) -> None:
    app.open()
    archive, forecast = app.mock.calls("archive"), app.mock.calls("forecast")
    assert [(c["start_date"], c["end_date"]) for c in archive] == [("2026-03-09", "2026-03-11")]
    assert [(c["start_date"], c["end_date"]) for c in forecast] == [("2026-03-12", "2026-03-15")]
    assert all(c["timezone"] == "Asia/Bangkok" for c in archive + forecast)


def test_loading_overlay_shown_while_fetching(app: App) -> None:
    app.mock.hold = True
    app.open(wait=False)
    page = app.page

    expect(page.locator("#loading")).to_be_visible()
    expect(page.locator("#status")).to_contain_text("Loading Hanoi, Vietnam (Last 7 days)")
    expect(page.locator("body")).to_have_class("is-loading")

    app.mock.release()
    app.wait_for_chart()
    expect(page.locator("body")).not_to_have_class("is-loading")


# ---- Time range ----------------------------------------------------------


def test_long_range_switches_to_daily(app: App) -> None:
    app.open()
    app.page.select_option("#range-select", "3m")
    expect(app.page.locator("#range-subtitle")).to_have_text(
        "Dec 16, 2025 – Mar 15, 2026 · Daily · Asia/Bangkok"
    )
    app.wait_for_chart()

    kpis = app.kpis()
    assert kpis["coverage"]["sub"] == "90 daily readings"
    assert kpis["aqi"]["value"] == "40Good"  # daily mean of the synthetic wave
    # Daily low/high come from the min/max columns, not the daily mean.
    assert kpis["temperature"]["sub"].startswith("Low 1")
    assert kpis["humidity"]["value"] != "—"
    assert app.prefs()["range"] == "3m"  # type: ignore[index]


def test_one_day_range_is_hourly(app: App) -> None:
    app.open()
    app.page.select_option("#range-select", "1d")
    expect(app.page.locator("#kpis")).to_contain_text("24 hourly readings")
    assert app.heading()[1] == "Mar 15, 2026 · Hourly · Asia/Bangkok"


# ---- Location autocomplete ----------------------------------------------


def test_autocomplete_lists_matches_and_keyboard_selects(app: App) -> None:
    app.open()
    page = app.page
    loc = page.locator("#location-input")
    items = page.locator("#location-suggestions li")

    loc.fill("Lon")
    expect(items).to_have_text(
        ["London, England, United Kingdom", "Longyearbyen, Svalbard and Jan Mayen"]
    )

    loc.press("ArrowDown")
    expect(items.nth(0)).to_have_class("active")
    loc.press("ArrowDown")
    expect(items.nth(1)).to_have_class("active")
    loc.press("ArrowUp")
    expect(items.nth(0)).to_have_class("active")
    loc.press("Enter")

    expect(page.locator("#location-suggestions")).to_be_hidden()
    expect(loc).to_have_value("London, England, United Kingdom")
    expect(app.page.locator("#place-title")).to_have_text("London, United Kingdom")
    assert app.prefs()["location"] == "London, England, United Kingdom"  # type: ignore[index]


def test_autocomplete_mouse_selection(app: App) -> None:
    app.open()
    page = app.page
    page.locator("#location-input").fill("Tok")
    page.locator("#location-suggestions li", has_text="Tokyo").click()
    expect(page.locator("#location-input")).to_have_value("Tokyo, Tokyo, Japan")
    expect(app.page.locator("#place-title")).to_have_text("Tokyo, Japan")


def test_autocomplete_needs_two_chars_and_hides_on_escape_or_outside_click(app: App) -> None:
    app.open()
    page = app.page
    loc = page.locator("#location-input")
    suggestions = page.locator("#location-suggestions")

    loc.fill("L")
    page.wait_for_timeout(400)  # past the 250ms debounce
    expect(suggestions).to_be_hidden()

    loc.fill("Lo")
    expect(suggestions).to_be_visible()
    loc.press("Escape")
    expect(suggestions).to_be_hidden()

    loc.fill("Lon")
    expect(suggestions).to_be_visible()
    page.locator("h1.brand").click()
    expect(suggestions).to_be_hidden()


def test_free_text_enter_geocodes_and_loads(app: App) -> None:
    app.open()
    loc = app.page.locator("#location-input")
    loc.fill("Tokyo")
    expect(app.page.locator("#location-suggestions")).to_be_visible()
    loc.press("Escape")
    loc.press("Enter")
    expect(app.page.locator("#place-title")).to_have_text("Tokyo, Japan")


def test_suggestion_labels_are_html_escaped(app: App) -> None:
    evil = Place("<img src=x onerror=window.__pwned=1>", "Nowhere", None, -45.0, 0.0, "UTC", 0.0)
    app.mock.places = (*app.mock.places, evil)
    app.open()
    app.page.locator("#location-input").fill("<img")
    item = app.page.locator("#location-suggestions li")
    expect(item).to_have_text("<img src=x onerror=window.__pwned=1>, Nowhere")
    assert app.page.locator("#location-suggestions img").count() == 0
    assert app.page.evaluate("() => window.__pwned") is None


# ---- Errors ---------------------------------------------------------------


def test_unknown_location_shows_dismissable_error(app: App) -> None:
    app.open()
    page = app.page
    loc = page.locator("#location-input")
    loc.fill("Atlantis")
    page.wait_for_timeout(400)
    loc.press("Enter")

    banner = page.locator("#error-banner")
    expect(banner).to_be_visible()
    expect(banner).to_contain_text('No matches for "Atlantis"')
    expect(page.locator("#loading")).to_be_hidden()

    page.locator("#error-banner-close").click()
    expect(banner).to_be_hidden()


def test_weather_api_failure_shows_error(app: App) -> None:
    app.mock.fail["forecast"] = 500
    app.open(wait=False)
    banner = app.page.locator("#error-banner")
    expect(banner).to_contain_text("Failed to fetch data")
    expect(banner).to_contain_text("mock forecast failure")
    expect(app.page.locator("#loading")).to_be_hidden()
    expect(app.page.locator("#kpis")).to_be_hidden()


def test_air_quality_failure_still_renders_weather(app: App) -> None:
    app.mock.fail["air-quality"] = 503
    app.open()
    expect(app.page.locator("#error-banner")).to_be_hidden()
    kpis = app.kpis()
    assert kpis["temperature"]["value"] == "25.0 °C"
    assert kpis["aqi"] == {
        "label": "Peak AQI (US)",
        "value": "—",
        "sub": "No air-quality data for this period",
    }
    assert kpis["coverage"]["value"] == "0%"
    aqi_card = app.page.locator('[data-chart="aqi"]')
    expect(aqi_card.locator(".card-empty")).to_contain_text("No air-quality data")
    expect(aqi_card.locator(".chart-wrap")).to_be_hidden()
    expect(aqi_card.locator('[data-action="table"]')).to_be_hidden()
    assert app.traces("aqi") == []


def test_request_timeout_after_30s(app: App) -> None:
    app.mock.hold = True
    app.open(wait=False)
    expect(app.page.locator("#loading")).to_be_visible()

    app.page.clock.fast_forward(31_000)
    banner = app.page.locator("#error-banner")
    expect(banner).to_contain_text("Request timed out after 30s")
    expect(app.page.locator("#loading")).to_be_hidden()


# ---- Theme ----------------------------------------------------------------


def test_theme_switch_restyles_page_and_chart(app: App) -> None:
    app.open()
    page = app.page
    html = page.locator("html")
    expect(html).to_have_attribute("data-theme", "light")
    assert app.layout()["paper_bgcolor"] == "#fcfcfb"

    page.select_option("#theme-select", "dark")
    expect(html).to_have_attribute("data-theme", "dark")
    page.wait_for_function(
        "() => document.getElementById('chart-temperature').layout.paper_bgcolor === '#1a1a19'"
    )
    # Body background has a 0.2s CSS transition; to_have_css retries until it settles.
    expect(page.locator("body")).to_have_css("background-color", "rgb(13, 13, 13)")
    assert app.prefs()["theme"] == "dark"  # type: ignore[index]
    # Re-theming reuses the cached history instead of refetching.
    assert len(app.mock.calls("forecast")) == 1


def test_system_theme_follows_os_preference(app: App) -> None:
    app.page.emulate_media(color_scheme="dark")
    app.open()
    expect(app.page.locator("#theme-select")).to_have_value("system")
    expect(app.page.locator("html")).to_have_attribute("data-theme", "dark")

    app.page.emulate_media(color_scheme="light")
    expect(app.page.locator("html")).to_have_attribute("data-theme", "light")
    app.page.wait_for_function(
        "() => document.getElementById('chart-temperature').layout.paper_bgcolor === '#fcfcfb'"
    )


# ---- Preferences & shareable URLs ------------------------------------------


def test_preferences_persist_across_reload(app: App) -> None:
    app.open()
    page = app.page
    page.select_option("#range-select", "2w")
    page.select_option("#theme-select", "dark")
    page.locator("#location-input").fill("Lon")
    page.locator("#location-suggestions li").first.click()

    page.reload()
    app.wait_for_chart()
    expect(page.locator("#location-input")).to_have_value("London, England, United Kingdom")
    expect(page.locator("#range-select")).to_have_value("2w")
    expect(page.locator("#theme-select")).to_have_value("dark")
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    expect(app.page.locator("#place-title")).to_have_text("London, United Kingdom")
    assert app.kpis()["coverage"]["sub"] == f"{14 * 24} hourly readings"


def test_url_params_override_saved_prefs(app: App) -> None:
    saved: dict[str, Any] = {"location": "London", "range": "1d", "theme": "light"}
    app.page.add_init_script(
        f"localStorage.setItem('{PREFS_KEY}', {json.dumps(json.dumps(saved))})"
    )
    app.open("?location=Tokyo&range=1m&theme=dark")
    page = app.page
    expect(page.locator("#location-input")).to_have_value("Tokyo")
    expect(page.locator("#range-select")).to_have_value("1m")
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    expect(app.page.locator("#place-title")).to_have_text("Tokyo, Japan")
    assert app.kpis()["coverage"]["sub"] == f"{30 * 24} hourly readings"


def test_corrupt_saved_prefs_fall_back_to_defaults(app: App) -> None:
    app.page.add_init_script(f"localStorage.setItem('{PREFS_KEY}', '{{not json')")
    app.open()
    expect(app.page.locator("#location-input")).to_have_value("Hanoi, Vietnam")
    expect(app.page.locator("#range-select")).to_have_value("1w")


def test_reset_preferences(app: App) -> None:
    app.open("?location=Tokyo&range=1d&theme=dark")
    page = app.page
    page.locator("#reset-prefs").click()
    expect(page.locator("#location-input")).to_have_value("Hanoi, Vietnam")
    expect(page.locator("#range-select")).to_have_value("1w")
    expect(page.locator("#theme-select")).to_have_value("system")
    expect(page.locator("#kpis")).to_contain_text("168 hourly readings")
    expect(app.page.locator("#place-title")).to_have_text("Hanoi, Vietnam")
