"""Fixtures for browser (Playwright) tests of the static frontend in ``web/``.

The site is built with ``scripts/build_site.py`` (app + one page per city) and
served by a throwaway static HTTP server — the same way GitHub Pages serves it —
and every outbound request is intercepted:

- Open-Meteo APIs  → :class:`OpenMeteoMock` (deterministic payloads)
- Plotly CDN       → a locally cached copy of the exact pinned bundle
- anything else    → aborted, so tests never hit the real network

The browser clock is pinned to ``FIXED_NOW`` so date ranges, chart titles and
observation counts are reproducible. Pages open in English unless a test asks
for ``lang="vi"`` (the site's default and indexed language).
"""

from __future__ import annotations

import functools
import sys
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import httpx
import pytest
from playwright.sync_api import Browser, Page, expect

from tests.e2e.openmeteo_mock import OpenMeteoMock

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "web"
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import build_site  # noqa: E402

PLOTLY_URL = "https://cdn.plot.ly/plotly-basic-2.35.2.min.js"
PLOTLY_CACHE = REPO_ROOT / ".cache" / "e2e" / PLOTLY_URL.rsplit("/", 1)[-1]

# 2026-03-15 12:00 in Asia/Ho_Chi_Minh (a Sunday). "Last 7 days" therefore
# resolves to 2026-03-09 → 2026-03-15.
FIXED_NOW = datetime(2026, 3, 15, 5, 0, tzinfo=UTC)
BROWSER_TZ = "Asia/Ho_Chi_Minh"

PREFS_KEY = "weahist.prefs.v1"
LANG_KEY = "weahist.lang"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    here = Path(__file__).parent
    for item in items:
        if here in item.path.parents:
            item.add_marker(pytest.mark.e2e)


# ---- Static server -----------------------------------------------------
class _QuietHandler(SimpleHTTPRequestHandler):
    # Windows' registry can map .js to text/plain, which browsers refuse to
    # execute as an ES module.
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".js": "text/javascript",
        ".css": "text/css",
        ".html": "text/html",
    }

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        pass

    def send_error(self, code: int, message: str | None = None, explain: str | None = None) -> None:
        # Like GitHub Pages: unknown paths get the site's 404.html (with a 404 status).
        page = Path(self.directory) / "404.html"
        if code != 404 or not page.exists():
            super().send_error(code, message, explain)
            return
        body = page.read_bytes()
        self.send_response(404)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)


@pytest.fixture(scope="session")
def site_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The deployable site, built from web/ exactly as CI builds it."""
    out = tmp_path_factory.mktemp("site") / "_site"
    build_site.build(WEB_DIR, out, base_path="/", lastmod="2026-03-15")
    return out


@pytest.fixture(scope="session")
def base_url(site_dir: Path) -> Iterator[str]:
    """Overrides pytest-base-url so ``page.goto("/")`` hits our server."""
    handler = functools.partial(_QuietHandler, directory=str(site_dir))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture(scope="session")
def plotly_js() -> bytes:
    """The pinned Plotly bundle, downloaded once and cached under ``.cache/``."""
    if not PLOTLY_CACHE.exists():
        try:
            resp = httpx.get(PLOTLY_URL, timeout=60, follow_redirects=True)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            pytest.skip(f"cannot download {PLOTLY_URL} for e2e tests: {exc}")
        PLOTLY_CACHE.parent.mkdir(parents=True, exist_ok=True)
        PLOTLY_CACHE.write_bytes(resp.content)
    return PLOTLY_CACHE.read_bytes()


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict[str, Any], base_url: str) -> dict[str, Any]:
    return {
        **browser_context_args,
        "base_url": base_url,
        "timezone_id": BROWSER_TZ,
        "locale": "en-US",
        "viewport": {"width": 1280, "height": 800},
        "color_scheme": "light",
        # Requests from a service worker would bypass the page-level mocks.
        "service_workers": "block",
    }


# ---- App driver --------------------------------------------------------
@dataclass
class App:
    page: Page
    mock: OpenMeteoMock
    errors: list[str] = field(default_factory=list)

    def open(self, query: str = "", *, wait: bool = True) -> App:
        self.page.goto(f"/{query}")
        if wait:
            self.wait_for_chart()
        return self

    def wait_for_chart(self) -> None:
        expect(self.page.locator("#kpis")).to_be_visible()
        expect(self.page.locator("#loading")).to_be_hidden()

    def layout(self, chart: str = "temperature") -> dict[str, Any]:
        """The Plotly layout rendered in a chart card (temperature/humidity/aqi)."""
        return self.page.evaluate(  # type: ignore[no-any-return]
            "(id) => document.getElementById(id).layout", f"chart-{chart}"
        )

    def traces(self, chart: str = "temperature") -> list[dict[str, Any]]:
        return self.page.evaluate(  # type: ignore[no-any-return]
            "(id) => (document.getElementById(id).data || [])"
            ".map(t => ({name: t.name, n: (t.x || []).length}))",
            f"chart-{chart}",
        )

    def heading(self) -> tuple[str, str]:
        """(card title, subtitle) rendered above the chart."""
        return (
            self.page.locator("#place-title").inner_text(),
            self.page.locator("#range-subtitle").inner_text(),
        )

    def kpis(self) -> dict[str, dict[str, str]]:
        """KPI tiles keyed by ``data-kpi`` → {"label", "value", "sub"}."""
        return self.page.evaluate(  # type: ignore[no-any-return]
            """() => Object.fromEntries(
                [...document.querySelectorAll('#kpis .kpi')].map(el => [el.dataset.kpi, {
                    label: el.querySelector('.kpi-label').textContent,
                    value: el.querySelector('.kpi-value').textContent,
                    sub: el.querySelector('.kpi-sub').textContent,
                }]))"""
        )

    def prefs(self) -> dict[str, Any] | None:
        return self.page.evaluate(  # type: ignore[no-any-return]
            f"() => JSON.parse(localStorage.getItem('{PREFS_KEY}'))"
        )


def _prepare(
    page: Page, base_url: str, plotly_js: bytes, mock: OpenMeteoMock, lang: str | None = "en"
) -> App:
    app = App(page=page, mock=mock)
    page.on("pageerror", lambda exc: app.errors.append(str(exc)))
    if lang:
        # Only when unset, so a test that switches language keeps it across reloads.
        page.add_init_script(
            f"if (!localStorage.getItem('{LANG_KEY}')) localStorage.setItem('{LANG_KEY}', '{lang}')"
        )

    # Routes registered later take precedence, so the catch-all goes first.
    def block_external(route: Any) -> None:
        if route.request.url.startswith(base_url):
            route.continue_()
        else:
            route.abort()

    page.route("**/*", block_external)
    page.route(
        PLOTLY_URL,
        lambda route: route.fulfill(
            status=200, body=plotly_js, content_type="application/javascript"
        ),
    )
    mock.install(page)
    page.clock.install(time=FIXED_NOW)
    return app


@pytest.fixture()
def mock() -> OpenMeteoMock:
    return OpenMeteoMock()


@pytest.fixture()
def app(page: Page, base_url: str, plotly_js: bytes, mock: OpenMeteoMock) -> Iterator[App]:
    driver = _prepare(page, base_url, plotly_js, mock)
    yield driver
    mock.abort_held()
    assert driver.errors == [], f"uncaught JS errors: {driver.errors}"


@pytest.fixture()
def make_app(
    browser: Browser,
    browser_context_args: dict[str, Any],
    base_url: str,
    plotly_js: bytes,
    mock: OpenMeteoMock,
) -> Iterator[Callable[..., App]]:
    """Factory for an :class:`App` in a fresh context with custom options
    (viewport, ``has_touch``, ``color_scheme`` …)."""
    contexts = []
    drivers: list[App] = []

    def factory(lang: str | None = "en", **overrides: Any) -> App:
        ctx = browser.new_context(**{**browser_context_args, **overrides})
        contexts.append(ctx)
        driver = _prepare(ctx.new_page(), base_url, plotly_js, mock, lang)
        drivers.append(driver)
        return driver

    yield factory
    for ctx in contexts:
        ctx.close()
    for driver in drivers:
        assert driver.errors == [], f"uncaught JS errors: {driver.errors}"
