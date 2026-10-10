"""City URLs: /<slug>/ for places with a static page, ?location= otherwise,
with working back/forward navigation."""

from __future__ import annotations

from playwright.sync_api import expect

from tests.e2e.conftest import App


def _pick(app: App, query: str, option: str) -> None:
    app.page.locator("#location-input").fill(query)
    app.page.locator("#location-suggestions li[role=option]", has_text=option).click()


def test_picking_a_city_with_a_page_moves_to_its_url(app: App) -> None:
    app.open()
    page = app.page
    page.evaluate("() => { window.__sameDocument = true; }")

    _pick(app, "Tok", "Tokyo")
    expect(page.locator("#place-title")).to_have_text("Tokyo, Japan")
    expect(page).to_have_url(f"{app.page.url.split('/tokyo/')[0]}/tokyo/")
    assert page.evaluate("() => window.__sameDocument") is True, "no full page reload"
    expect(page).to_have_title("Tokyo, Japan weather history: temperature, humidity, AQI")
    assert (
        page.locator('link[rel="canonical"]').get_attribute("href")
        == "https://tnam0x.github.io/weahist/tokyo/"
    )
    expect(page.locator("#page-intro")).to_contain_text("Tokyo, Japan")


def test_places_without_a_page_use_a_query(app: App) -> None:
    app.open()
    _pick(app, "Longy", "Longyearbyen")
    expect(app.page.locator("#place-title")).to_contain_text("Longyearbyen")
    assert app.page.url.endswith("/?location=Longyearbyen%2C+Svalbard+and+Jan+Mayen")
    assert (
        app.page.locator('link[rel="canonical"]').get_attribute("href")
        == "https://tnam0x.github.io/weahist/"
    )


def test_back_and_forward_restore_places(app: App) -> None:
    app.open("tokyo/")
    page = app.page
    _pick(app, "Lon", "London")
    expect(page.locator("#place-title")).to_have_text("London, United Kingdom")
    assert page.url.endswith("/london/")

    page.go_back()
    expect(page.locator("#place-title")).to_have_text("Tokyo, Japan")
    expect(page.locator("#location-input")).to_have_value("Tokyo, Japan")
    assert page.url.endswith("/tokyo/")

    page.go_forward()
    expect(page.locator("#place-title")).to_have_text("London, United Kingdom")


def test_range_and_units_replace_instead_of_push(app: App) -> None:
    app.open("hanoi/")
    page = app.page
    length = page.evaluate("() => history.length")
    page.locator('[data-range="3d"]').click()
    expect(page.locator("#kpis")).to_contain_text("72 hourly readings")
    page.locator('[data-units="f"]').click()
    expect(page).to_have_url(f"{page.url.split('/hanoi/')[0]}/hanoi/?range=3d&units=f")
    assert page.evaluate("() => history.length") == length


def test_city_url_wins_over_saved_place(app: App) -> None:
    app.open()
    _pick(app, "Lon", "London")
    expect(app.page.locator("#place-title")).to_have_text("London, United Kingdom")
    app.page.goto("/da-nang/")
    app.wait_for_chart()
    expect(app.page.locator("#place-title")).to_have_text("Da Nang, Vietnam")


def test_brand_links_home_from_a_city_page(app: App) -> None:
    app.open("hanoi/")
    app.page.locator(".brand-link").click()
    app.wait_for_chart()
    assert app.page.url.endswith("/")
    expect(app.page.locator("#page-intro")).to_contain_text("any city")
