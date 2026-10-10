"""Service worker: offline use after one visit, cache versioning."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import Browser, BrowserContext, Route, expect

from tests.e2e.conftest import FIXED_NOW, LANG_KEY, PLOTLY_URL
from tests.e2e.openmeteo_mock import OPEN_METEO_PATTERN, OpenMeteoMock


@pytest.fixture()
def sw_context(
    browser: Browser,
    browser_context_args: dict[str, Any],
    base_url: str,
    plotly_js: bytes,
    mock: OpenMeteoMock,
) -> Iterator[BrowserContext]:
    """A context with service workers enabled. Routes are set on the context,
    not the page, so requests the worker makes itself are mocked as well."""
    ctx = browser.new_context(**{**browser_context_args, "service_workers": "allow"})

    # Playwright still runs route handlers while the context is "offline", so
    # every route checks the emulated state and fails like a dead network.
    def offline_or(handler: Callable[[Route], None]) -> Callable[[Route], None]:
        def route(r: Route) -> None:
            if ctx.offline:  # type: ignore[attr-defined]
                r.abort("internetdisconnected")
            else:
                handler(r)

        return route

    ctx.offline = False  # type: ignore[attr-defined]
    ctx.route(
        "**/*",
        offline_or(lambda r: r.continue_() if r.request.url.startswith(base_url) else r.abort()),
    )
    ctx.route(
        PLOTLY_URL,
        offline_or(
            lambda r: r.fulfill(status=200, body=plotly_js, content_type="application/javascript")
        ),
    )
    ctx.route(OPEN_METEO_PATTERN, offline_or(mock._handle))
    ctx.add_init_script(f"localStorage.setItem('{LANG_KEY}', 'en')")
    yield ctx
    ctx.close()


def test_works_offline_after_one_visit(sw_context: BrowserContext, mock: OpenMeteoMock) -> None:
    page = sw_context.new_page()
    page.clock.install(time=FIXED_NOW)
    page.goto("/")
    expect(page.locator("#kpis")).to_be_visible()
    page.evaluate("() => navigator.serviceWorker.ready.then(() => true)")

    # The first visit wasn't controlled by the worker yet; this one is, and
    # leaves the shell, Plotly and the data in its caches.
    page.reload()
    expect(page.locator("#kpis")).to_contain_text("168 hourly readings")
    assert page.evaluate("() => Boolean(navigator.serviceWorker.controller)")
    expect(page.locator("#offline-banner")).to_be_hidden()

    sw_context.set_offline(True)
    sw_context.offline = True  # type: ignore[attr-defined]
    requests = len(mock.requests)
    page.reload()
    expect(page.locator("#offline-banner")).to_be_visible()
    expect(page.locator("#kpis")).to_contain_text("168 hourly readings")
    expect(page.locator("#chart-temperature .main-svg").first).to_be_visible()
    expect(page.locator("#error-banner")).to_be_hidden()
    assert len(mock.requests) == requests, "offline data must come from the worker's cache"

    sw_context.set_offline(False)
    sw_context.offline = False  # type: ignore[attr-defined]
    expect(page.locator("#offline-banner")).to_be_hidden()


def test_build_versions_the_worker_and_its_shell_exists(site_dir: Path) -> None:
    source = (site_dir / "sw.js").read_text(encoding="utf-8")
    build_id = re.search(r'const BUILD_ID = "([^"]+)";', source)
    assert build_id and re.fullmatch(r"[0-9a-f]{12}", build_id.group(1))
    shell = re.search(r"const SHELL_FILES = \[(.*?)\];", source, re.S)
    assert shell
    for name in re.findall(r'"([^"]+)"', shell.group(1)):
        assert (site_dir / name).exists(), f"shell file missing from the build: {name}"
