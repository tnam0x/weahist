"""End-to-end behaviour of the static frontend: loading, controls, prefs, errors."""

from __future__ import annotations

import json
from typing import Any

from playwright.sync_api import expect

from tests.e2e.conftest import PREFS_KEY, App, title_text
from tests.e2e.openmeteo_mock import Place

# ---- Initial load --------------------------------------------------------


def test_default_view_renders_hanoi_last_7_days(app: App) -> None:
    app.open()
    page = app.page

    expect(page.locator("#location-input")).to_have_value("Hanoi, Vietnam")
    expect(page.locator("#range-select")).to_have_value("1w")
    expect(page.locator("#status")).to_have_text("")
    expect(page.locator("#error-banner")).to_be_hidden()

    title = title_text(app.layout())
    assert "Weather & Air Quality — Hanoi, Vietnam" in title
    assert "2026-03-09 → 2026-03-15" in title
    assert "Hourly" in title

    assert app.summary() == {
        "Granularity": "Hourly",
        "Observations": "168",
        "Max temp": "30.0 °C",
        "Min temp": "20.0 °C",
        "Max AQI": "70",
        "Min AQI": "10",
        "AQI coverage": "100%",
    }
    names = [t["name"] for t in app.traces()]
    assert "AQI" in names
    assert any(n.startswith("Temp") for n in names)
    assert any("umidity" in n for n in names)


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
    expect(app.page.locator("#summary")).to_contain_text("Daily")
    app.wait_for_chart()

    summary = app.summary()
    assert summary["Granularity"] == "Daily"
    assert summary["Observations"] == "90"
    assert summary["Max AQI"] == "40"  # daily mean of the synthetic wave
    assert "2025-12-16 → 2026-03-15" in title_text(app.layout())
    assert app.prefs()["range"] == "3m"  # type: ignore[index]


def test_one_day_range_is_hourly(app: App) -> None:
    app.open()
    app.page.select_option("#range-select", "1d")
    expect(app.page.locator("#summary")).to_contain_text("Observations24")
    assert app.summary()["Granularity"] == "Hourly"


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
    expect(page.locator("#summary")).to_contain_text("15.0 °C")
    assert "London, United Kingdom" in title_text(app.layout())
    assert app.prefs()["location"] == "London, England, United Kingdom"  # type: ignore[index]


def test_autocomplete_mouse_selection(app: App) -> None:
    app.open()
    page = app.page
    page.locator("#location-input").fill("Tok")
    page.locator("#location-suggestions li", has_text="Tokyo").click()
    expect(page.locator("#location-input")).to_have_value("Tokyo, Tokyo, Japan")
    expect(page.locator("#summary")).to_contain_text("17.0 °C")
    assert "Tokyo, Japan" in title_text(app.layout())


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
    expect(app.page.locator("#summary")).to_contain_text("17.0 °C")
    assert "Tokyo, Japan" in title_text(app.layout())


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
    expect(app.page.locator("#summary")).to_be_hidden()


def test_air_quality_failure_still_renders_weather(app: App) -> None:
    app.mock.fail["air-quality"] = 503
    app.open()
    expect(app.page.locator("#error-banner")).to_be_hidden()
    summary = app.summary()
    assert summary["Max temp"] == "30.0 °C"
    assert "Max AQI" not in summary
    assert "AQI" not in [t["name"] for t in app.traces()]


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
    assert app.layout()["paper_bgcolor"] == "#FFFFFF"

    page.select_option("#theme-select", "dark")
    expect(html).to_have_attribute("data-theme", "dark")
    page.wait_for_function(
        "() => document.getElementById('chart').layout.paper_bgcolor === '#161B22'"
    )
    # Body background has a 0.2s CSS transition; to_have_css retries until it settles.
    expect(page.locator("body")).to_have_css("background-color", "rgb(13, 17, 23)")
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
        "() => document.getElementById('chart').layout.paper_bgcolor === '#FFFFFF'"
    )


# ---- Preferences & shareable URLs ------------------------------------------


def test_preferences_persist_across_reload(app: App) -> None:
    app.open()
    page = app.page
    page.select_option("#range-select", "2w")
    page.select_option("#theme-select", "dark")
    page.locator("#location-input").fill("Lon")
    page.locator("#location-suggestions li").first.click()
    expect(page.locator("#summary")).to_contain_text("15.0 °C")

    page.reload()
    app.wait_for_chart()
    expect(page.locator("#location-input")).to_have_value("London, England, United Kingdom")
    expect(page.locator("#range-select")).to_have_value("2w")
    expect(page.locator("#theme-select")).to_have_value("dark")
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    assert "London, United Kingdom" in title_text(app.layout())
    assert app.summary()["Observations"] == str(14 * 24)


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
    assert "Tokyo, Japan" in title_text(app.layout())
    assert app.summary()["Observations"] == str(30 * 24)


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
    expect(page.locator("#summary")).to_contain_text("Observations168")
    assert "Hanoi, Vietnam" in title_text(app.layout())
