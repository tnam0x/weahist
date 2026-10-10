"""In-memory response cache in api.js."""

from __future__ import annotations

from playwright.sync_api import expect

from tests.e2e.conftest import App


def _pick(app: App, key: str, readings: int) -> None:
    app.page.locator(f'[data-range="{key}"]').click()
    expect(app.page.locator("#kpis")).to_contain_text(f"{readings} hourly readings")
    expect(app.page.locator("body")).not_to_have_class("is-loading")


def test_revisiting_a_range_reuses_cached_responses(app: App) -> None:
    app.open()
    _pick(app, "3d", 72)
    before = len(app.mock.requests)
    _pick(app, "1w", 168)
    assert len(app.mock.requests) == before, "1w was already fetched this session"


def test_cache_expires_after_15_minutes(app: App) -> None:
    app.open()
    _pick(app, "3d", 72)
    app.page.clock.fast_forward("16:00")
    before = len(app.mock.calls("forecast"))
    _pick(app, "1w", 168)
    assert len(app.mock.calls("forecast")) == before + 1


def test_failed_responses_are_not_cached(app: App) -> None:
    app.mock.fail["forecast"] = 500
    app.open(wait=False)
    expect(app.page.locator("#error-banner")).to_contain_text("Failed to fetch data")

    del app.mock.fail["forecast"]
    app.page.locator('[data-range="1w"]').click()
    app.wait_for_chart()
    assert app.kpis()["coverage"]["sub"] == "168 hourly readings"
