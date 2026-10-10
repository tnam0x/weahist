"""SEO & link-preview metadata, static assets, city pages and crawlable content.

The site is indexed in Vietnamese, so these tests open pages with lang="vi".
"""

from __future__ import annotations

import json
import re
import struct
import xml.etree.ElementTree as ET
from collections.abc import Callable
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.conftest import WEB_DIR, App

SITE_URL = "https://tnam0x.github.io/weahist/"
CITIES = json.loads((WEB_DIR / "cities.json").read_text(encoding="utf-8"))


def _meta(page: Page, selector: str) -> str:
    value = page.locator(selector).first.get_attribute("content")
    assert value, f"{selector} is missing or empty"
    return value


def _png_size(data: bytes) -> tuple[int, int]:
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    return struct.unpack(">II", data[16:24])


def _ld(page: Page) -> dict:
    return json.loads(page.locator('script[type="application/ld+json"]').text_content() or "")


@pytest.fixture()
def head(make_app: Callable[..., App]) -> Page:
    return make_app(lang="vi").open().page


@pytest.fixture()
def hanoi(make_app: Callable[..., App]) -> Page:
    return make_app(lang="vi").open("hanoi/").page


# ---- Root page --------------------------------------------------------------


def test_title_and_description_fit_search_results(head: Page) -> None:
    title = head.title()
    assert 30 <= len(title) <= 65, f"title is {len(title)} chars: {title!r}"
    assert "thời tiết" in title.lower() and "không khí" in title
    description = _meta(head, 'meta[name="description"]')
    assert 70 <= len(description) <= 160, f"description is {len(description)} chars"
    expect(head.locator("html")).to_have_attribute("lang", "vi")


def test_canonical_points_at_the_site_root(head: Page) -> None:
    # Shared ?location=… links must all fold into one URL.
    assert head.locator('link[rel="canonical"]').get_attribute("href") == SITE_URL


def test_open_graph_and_twitter_cards(head: Page) -> None:
    assert _meta(head, 'meta[property="og:url"]') == SITE_URL
    assert _meta(head, 'meta[property="og:type"]') == "website"
    assert _meta(head, 'meta[property="og:locale"]') == "vi_VN"
    for name in ("og:title", "og:description", "og:image:alt"):
        _meta(head, f'meta[property="{name}"]')
    image = _meta(head, 'meta[property="og:image"]')
    assert image == f"{SITE_URL}og-image.png", "crawlers need an absolute image URL"
    assert _meta(head, 'meta[property="og:image:width"]') == "1200"
    assert _meta(head, 'meta[property="og:image:height"]') == "630"
    assert _meta(head, 'meta[name="twitter:card"]') == "summary_large_image"
    assert _meta(head, 'meta[name="twitter:image"]') == image


def test_structured_data_describes_a_free_web_app(head: Page) -> None:
    data = _ld(head)
    assert data["@context"] == "https://schema.org"
    assert data["@type"] == "WebApplication"
    assert data["url"] == SITE_URL
    assert data["isAccessibleForFree"] is True
    assert data["offers"]["price"] == "0"
    assert data["description"] == _meta(head, 'meta[name="description"]')


def test_single_h1_names_the_app(head: Page) -> None:
    expect(head.locator("h1")).to_have_count(1)
    assert head.locator("h1").inner_text().strip().endswith("Lịch sử Thời tiết")


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
    head: Page, base_url: str, path: str, size: tuple[int, int]
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


def test_sitemap_lists_root_and_every_city(head: Page, base_url: str) -> None:
    resp = head.request.get(f"{base_url}/sitemap.xml")
    assert resp.ok
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locs = [el.text for el in ET.fromstring(resp.body()).findall("s:url/s:loc", ns)]
    assert locs == [SITE_URL] + [f"{SITE_URL}{c['slug']}/" for c in CITIES]


def test_plotly_does_not_block_first_paint(head: Page) -> None:
    script = head.locator('script[src*="cdn.plot.ly"]')
    assert script.get_attribute("async") is not None or script.get_attribute("defer") is not None


def test_page_has_crawlable_text_without_javascript(make_app: Callable[..., App]) -> None:
    app = make_app(lang="vi")
    # No app bundle and no API: only the static HTML is left, as for a simple crawler.
    app.page.route("**/app.js", lambda route: route.abort())
    app.page.goto("/")
    expect(app.page.locator("h1")).to_contain_text("Lịch sử Thời tiết")
    text = app.page.locator("body").inner_text().lower()
    for keyword in ("nhiệt độ", "độ ẩm", "chất lượng không khí", "open-meteo"):
        assert keyword in text, keyword


def test_footer_links_to_every_city_page(head: Page) -> None:
    hrefs = head.locator(".city-index a").evaluate_all(
        "els => els.map(a => a.getAttribute('href'))"
    )
    assert hrefs == [f"./{c['slug']}/" for c in CITIES]


# ---- City pages -------------------------------------------------------------


def test_city_page_has_its_own_metadata(hanoi: Page) -> None:
    url = f"{SITE_URL}hanoi/"
    assert hanoi.title() == "Thời tiết Hà Nội, Việt Nam: lịch sử nhiệt độ, độ ẩm, AQI"
    assert hanoi.locator('link[rel="canonical"]').get_attribute("href") == url
    assert _meta(hanoi, 'meta[property="og:url"]') == url
    description = _meta(hanoi, 'meta[name="description"]')
    assert "Hà Nội" in description and len(description) <= 170

    data = _ld(hanoi)
    assert data["@type"] == "WebPage"
    assert data["url"] == url
    assert data["about"]["name"] == "Hà Nội"
    assert data["about"]["geo"]["latitude"] == pytest.approx(21.0245, abs=0.01)
    crumbs = data["breadcrumb"]["itemListElement"]
    assert [c["item"] for c in crumbs] == [SITE_URL, url]


def test_city_page_loads_its_city_without_geocoding(make_app: Callable[..., App]) -> None:
    app = make_app(lang="vi").open("tokyo/")
    expect(app.page.locator("#place-title")).to_have_text("Tokyo, Nhật Bản")
    expect(app.page.locator("#page-intro")).to_contain_text("Tokyo, Nhật Bản")
    assert app.mock.calls("geocoding") == []
    assert app.mock.calls("forecast")[0]["timezone"] == "Asia/Tokyo"


def test_city_pages_have_crawlable_text_without_javascript(make_app: Callable[..., App]) -> None:
    app = make_app(lang="vi")
    app.page.route("**/app.js", lambda route: route.abort())
    app.page.goto("/da-lat/")
    expect(app.page.locator("#place-title")).to_have_text("Đà Lạt, Việt Nam")
    expect(app.page.locator("#page-intro")).to_contain_text("Đà Lạt")
    # Assets resolve from one level down.
    expect(app.page.locator("body")).to_have_css("font-size", "14px")


def test_every_city_page_is_built(site_dir: Path) -> None:
    for city in CITIES:
        page = (site_dir / city["slug"] / "index.html").read_text(encoding="utf-8")
        assert f'<link rel="canonical" href="{SITE_URL}{city["slug"]}/" />' in page
        assert 'href="./' not in page, f"{city['slug']}: unrewritten relative link"
        assert re.search(r'id="page-city">\{.*"slug": "' + city["slug"], page)


def test_unknown_path_becomes_a_search(make_app: Callable[..., App]) -> None:
    app = make_app()
    app.page.goto("/longyearbyen/")
    app.wait_for_chart()
    assert app.page.url.endswith("/?location=longyearbyen")
    expect(app.page.locator("#place-title")).to_contain_text("Longyearbyen")
