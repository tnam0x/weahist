"""SEO & link-preview metadata, static assets, and crawlable content."""

from __future__ import annotations

import json
import struct
import xml.etree.ElementTree as ET
from collections.abc import Callable

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.conftest import App

SITE_URL = "https://tnam0x.github.io/weahist/"


def _meta(page: Page, selector: str) -> str:
    value = page.locator(selector).first.get_attribute("content")
    assert value, f"{selector} is missing or empty"
    return value


def _png_size(data: bytes) -> tuple[int, int]:
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    return struct.unpack(">II", data[16:24])


@pytest.fixture()
def head(app: App) -> Page:
    app.open()
    return app.page


def test_title_and_description_fit_search_results(head: Page) -> None:
    title = head.title()
    assert 30 <= len(title) <= 65, f"title is {len(title)} chars: {title!r}"
    assert "Weather" in title and "Air Quality" in title
    description = _meta(head, 'meta[name="description"]')
    assert 70 <= len(description) <= 160, f"description is {len(description)} chars"


def test_canonical_points_at_the_site_root(head: Page) -> None:
    # Shared links carry ?location=…&range=…; they must all fold into one URL.
    assert head.locator('link[rel="canonical"]').get_attribute("href") == SITE_URL


def test_open_graph_and_twitter_cards(head: Page) -> None:
    assert _meta(head, 'meta[property="og:url"]') == SITE_URL
    assert _meta(head, 'meta[property="og:type"]') == "website"
    for name in ("og:title", "og:description", "og:image:alt"):
        _meta(head, f'meta[property="{name}"]')
    image = _meta(head, 'meta[property="og:image"]')
    assert image == f"{SITE_URL}og-image.png", "crawlers need an absolute image URL"
    assert _meta(head, 'meta[property="og:image:width"]') == "1200"
    assert _meta(head, 'meta[property="og:image:height"]') == "630"
    assert _meta(head, 'meta[name="twitter:card"]') == "summary_large_image"
    assert _meta(head, 'meta[name="twitter:image"]') == image


def test_structured_data_describes_a_free_web_app(head: Page) -> None:
    raw = head.locator('script[type="application/ld+json"]').text_content()
    data = json.loads(raw or "")
    assert data["@context"] == "https://schema.org"
    assert data["@type"] == "WebApplication"
    assert data["url"] == SITE_URL
    assert data["isAccessibleForFree"] is True
    assert data["offers"]["price"] == "0"
    assert data["description"] == _meta(head, 'meta[name="description"]')


def test_single_h1_names_the_app(head: Page) -> None:
    expect(head.locator("h1")).to_have_count(1)
    assert head.locator("h1").inner_text().strip().endswith("Weather History")


@pytest.mark.parametrize(
    ("path", "size"),
    [
        ("og-image.png", (1200, 630)),
        ("apple-touch-icon.png", (180, 180)),
        ("icon-192.png", (192, 192)),
        ("icon-512.png", (512, 512)),
    ],
)
def test_images_exist_with_declared_sizes(
    head: Page, base_url: str, path: str, size: tuple
) -> None:
    resp = head.request.get(f"{base_url}/{path}")
    assert resp.ok, f"{path} → HTTP {resp.status}"
    assert _png_size(resp.body()) == size


def test_icons_and_manifest_resolve(head: Page, base_url: str) -> None:
    for selector in ('link[rel="icon"]', 'link[rel="apple-touch-icon"]', 'link[rel="manifest"]'):
        href = head.locator(selector).get_attribute("href")
        assert href, selector
        assert head.request.get(f"{base_url}/{href.lstrip('./')}").ok, f"{selector} → {href}"

    manifest = head.request.get(f"{base_url}/site.webmanifest").json()
    assert manifest["name"] == "Weather History"
    for icon in manifest["icons"]:
        assert head.request.get(f"{base_url}/{icon['src']}").ok, icon["src"]


def test_sitemap_lists_the_canonical_url(head: Page, base_url: str) -> None:
    resp = head.request.get(f"{base_url}/sitemap.xml")
    assert resp.ok
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locs = [el.text for el in ET.fromstring(resp.body()).findall("s:url/s:loc", ns)]
    assert locs == [SITE_URL]


def test_plotly_does_not_block_first_paint(head: Page) -> None:
    script = head.locator('script[src*="cdn.plot.ly"]')
    assert script.get_attribute("defer") is not None


def test_page_has_crawlable_text_without_javascript_data(make_app: Callable[..., App]) -> None:
    app = make_app()
    # No app bundle and no API: only the static HTML is left, as for a simple crawler.
    app.page.route("**/app.js", lambda route: route.abort())
    app.page.goto("/")
    expect(app.page.locator("h1")).to_contain_text("Weather History")
    about = app.page.locator(".app-footer .about")
    expect(about).to_be_visible()
    text = about.inner_text().lower()
    for keyword in ("temperature", "humidity", "air quality index", "open-meteo"):
        assert keyword in text, keyword
