"""Vietnamese / English UI: default language, switching, formatting, and the
static texts the site build repeats."""

from __future__ import annotations

import html
import re
from collections.abc import Callable

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.conftest import LANG_KEY, WEB_DIR, App, build_site


def _strings(page: Page, lang: str) -> dict[str, str]:
    return page.evaluate("async (lang) => (await import('/i18n.js')).strings(lang)", lang)


def test_vietnamese_is_the_default(make_app: Callable[..., App]) -> None:
    app = make_app(lang=None, locale="en-US").open()
    page = app.page
    expect(page.locator("html")).to_have_attribute("lang", "vi")
    expect(page.locator('label[for="location-input"]')).to_have_text("Địa điểm")
    expect(page.locator("#lang-toggle")).to_have_text("EN")
    expect(page.locator("#place-title")).to_have_text("Hà Nội, Việt Nam")
    assert app.heading()[1] == "9 thg 3, 2026 – 15 thg 3, 2026 · Theo giờ · Asia/Bangkok"
    assert app.kpis()["temperature"] == {
        "label": "Nhiệt độ TB",
        "value": "25,0 °C",
        "sub": "Thấp 20,0 · Cao 30,0 °C",
    }
    assert app.kpis()["aqi"]["value"] == "70Trung bình"
    assert app.kpis()["coverage"]["sub"] == "168 số liệu theo giờ"


def test_switching_language_relabels_everything_in_place(make_app: Callable[..., App]) -> None:
    app = make_app(lang="vi").open()
    page = app.page
    requests = len(app.mock.requests)

    page.locator("#lang-toggle").click()
    expect(page.locator("html")).to_have_attribute("lang", "en")
    expect(page.locator("#lang-toggle")).to_have_text("VI")
    expect(page.locator('label[for="location-input"]')).to_have_text("Location")
    expect(page.locator('[data-range="1w"]')).to_have_text("7d")
    expect(page.locator("#place-title")).to_have_text("Hanoi, Vietnam")
    expect(page.locator("#location-input")).to_have_value("Hanoi, Vietnam")
    expect(page.locator('[data-kpi="temperature"] .kpi-value')).to_have_text("25.0 °C")
    expect(page.locator('[data-chart="aqi"] .band-legend li')).to_have_text(["Good", "Moderate"])
    assert app.layout()["separators"] == ".,"
    assert len(app.mock.requests) == requests, "switching language must not refetch"

    page.reload()
    app.wait_for_chart()
    expect(page.locator("html")).to_have_attribute("lang", "en")
    assert page.evaluate(f"() => localStorage.getItem('{LANG_KEY}')") == "en"


def test_vietnamese_charts_use_local_number_and_date_formats(make_app: Callable[..., App]) -> None:
    app = make_app(lang="vi").open("?range=3m")
    layout = app.layout()
    assert layout["separators"] == ",."
    assert layout["xaxis"]["hoverformat"] == "%a %-d/%-m/%Y"
    assert [t["name"] for t in app.traces()] == ["Cao", "Thấp", "TB"]
    labels = app.page.locator("#chart-temperature .annotation").all_text_contents()
    assert any(re.fullmatch(r"cao \d+,\d °C", label) for label in labels), labels


def test_vietnamese_errors_and_validation(make_app: Callable[..., App]) -> None:
    app = make_app(lang="vi").open()
    page = app.page
    page.locator("#custom-toggle").click()
    page.locator("#custom-start").fill("2026-03-10")
    page.locator("#custom-end").fill("2026-03-01")
    page.locator("#custom-range button[type=submit]").click()
    expect(page.locator("#custom-error")).to_have_text(
        "Ngày bắt đầu phải trước hoặc bằng ngày kết thúc."
    )


def test_every_key_is_translated(make_app: Callable[..., App]) -> None:
    page = make_app().open().page
    vi, en = _strings(page, "vi"), _strings(page, "en")
    assert set(vi) == set(en)
    used = set(
        re.findall(
            r'data-i18n(?:-aria|-title|-placeholder)?="([^"]+)"',
            (WEB_DIR / "index.html").read_text(encoding="utf-8"),
        )
    )
    assert used <= set(vi), used - set(vi)


def test_static_html_matches_the_vietnamese_strings(make_app: Callable[..., App]) -> None:
    # The HTML ships Vietnamese text for crawlers; it must say what the app would.
    page = make_app().open().page
    vi = _strings(page, "vi")
    source = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    for key, text in re.findall(r'data-i18n="([^"]+)"[^>]*>([^<]+)<', source):
        assert html.unescape(" ".join(text.split())) == vi[key], key


def test_build_texts_match_the_app(make_app: Callable[..., App]) -> None:
    page = make_app().open().page
    vi = _strings(page, "vi")
    assert vi["meta.title"] == build_site.ROOT_TITLE
    assert vi["meta.description"] == build_site.ROOT_DESCRIPTION
    assert vi["meta.titleCity"] == build_site.CITY_TITLE
    assert vi["intro.city"] == build_site.CITY_DESCRIPTION


@pytest.mark.parametrize("lang", ["vi", "en"])
def test_header_fits_small_phones_in_both_languages(
    make_app: Callable[..., App], lang: str
) -> None:
    app = make_app(lang=lang, viewport={"width": 320, "height": 640}, has_touch=True).open()
    scroll_w, client_w = app.page.evaluate(
        "() => [document.documentElement.scrollWidth, document.documentElement.clientWidth]"
    )
    assert scroll_w <= client_w
