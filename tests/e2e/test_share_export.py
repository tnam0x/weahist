"""Share link, CSV export and per-card PNG export."""

from __future__ import annotations

import csv
import io
from collections.abc import Callable
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import expect

from tests.e2e.conftest import App

CLIPBOARD = ["clipboard-read", "clipboard-write"]


def _clipboard_query(app: App) -> dict[str, list[str]]:
    url = app.page.evaluate("() => navigator.clipboard.readText()")
    return parse_qs(urlparse(url).query)


def test_share_copies_a_link_to_the_current_view(make_app: Callable[..., App]) -> None:
    app = make_app(permissions=CLIPBOARD).open()
    page = app.page
    page.locator("#share").click()
    expect(page.locator("#toast")).to_have_text("Link copied")
    # Defaults (system theme, °C) stay out of the link.
    assert _clipboard_query(app) == {"location": ["Hanoi, Vietnam"], "range": ["1w"]}

    page.locator('[data-units="f"]').click()
    page.select_option("#theme-select", "dark")
    page.locator("#custom-toggle").click()
    page.locator("#custom-start").fill("2026-03-01")
    page.locator("#custom-end").fill("2026-03-05")
    page.get_by_role("button", name="Apply").click()
    app.wait_for_chart()
    page.locator("#share").click()
    assert _clipboard_query(app) == {
        "location": ["Hanoi, Vietnam"],
        "start": ["2026-03-01"],
        "end": ["2026-03-05"],
        "units": ["f"],
        "theme": ["dark"],
    }


def test_shared_link_reopens_the_same_view(make_app: Callable[..., App]) -> None:
    sender = make_app(permissions=CLIPBOARD).open("?location=Tokyo&range=3d&units=f")
    sender.page.locator("#share").click()
    url = sender.page.evaluate("() => navigator.clipboard.readText()")

    receiver = make_app()
    receiver.page.goto(url)
    receiver.wait_for_chart()
    expect(receiver.page.locator("#place-title")).to_have_text("Tokyo, Japan")
    expect(receiver.page.locator('[data-range="3d"]')).to_have_attribute("aria-checked", "true")
    expect(receiver.page.locator('[data-kpi="temperature"] .kpi-value')).to_contain_text("°F")


def test_share_uses_native_sheet_on_touch_devices(make_app: Callable[..., App]) -> None:
    app = make_app(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
    app.page.add_init_script(
        "navigator.share = (data) => { window.__shared = data; return Promise.resolve(); };"
    )
    app.open()
    expect(app.page.locator("#share .btn-label")).to_be_hidden()  # icon-only on phones
    app.page.locator("#share").click()
    app.page.wait_for_function("() => window.__shared")
    shared = app.page.evaluate("() => window.__shared")
    assert shared["title"] == "Weather History"
    assert "location=Hanoi%2C+Vietnam" in shared["url"]


def test_csv_download_hourly(app: App, tmp_path: Path) -> None:
    app.open()
    with app.page.expect_download() as info:
        app.page.locator("#download-csv").click()
    download = info.value
    assert download.suggested_filename == "weahist-hanoi-2026-03-09_2026-03-15.csv"
    path = tmp_path / download.suggested_filename
    download.save_as(path)
    rows = list(csv.reader(io.StringIO(path.read_text(encoding="utf-8"))))
    assert rows[0] == [
        "time",
        "temperature_C",
        "humidity_pct",
        "us_aqi",
        "pm2_5_ugm3",
        "pm10_ugm3",
    ]
    assert len(rows) == 1 + 168
    assert rows[1] == ["2026-03-09T00:00", "25", "70", "40", "12", "20"]


def test_csv_download_daily_in_fahrenheit(app: App, tmp_path: Path) -> None:
    app.open("?range=3m&units=f")
    with app.page.expect_download() as info:
        app.page.locator("#download-csv").click()
    path = tmp_path / "data.csv"
    info.value.save_as(path)
    rows = list(csv.reader(io.StringIO(path.read_text(encoding="utf-8"))))
    assert rows[0][:4] == ["time", "temperature_min_F", "temperature_mean_F", "temperature_max_F"]
    assert "humidity_mean_pct" in rows[0]
    assert len(rows) == 1 + 90
    low, mean, high = (float(v) for v in rows[1][1:4])
    assert low < mean < high


def test_png_download_per_card(app: App) -> None:
    app.open()
    card = app.page.locator('[data-chart="humidity"]')
    with app.page.expect_download() as info:
        card.locator('[data-action="png"]').click()
    assert info.value.suggested_filename == "weahist-hanoi-2026-03-09_2026-03-15-humidity.png"


def test_png_button_hidden_for_empty_card(app: App) -> None:
    app.mock.fail["air-quality"] = 503
    app.open()
    expect(app.page.locator('[data-chart="aqi"] [data-action="png"]')).to_be_hidden()
    expect(app.page.locator('[data-chart="temperature"] [data-action="png"]')).to_be_visible()
