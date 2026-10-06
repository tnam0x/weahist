"""Layout checks across phone, tablet and desktop viewports.

These assert geometry rather than pixels, so they're stable across OSes and
font rendering: nothing overflows horizontally, controls don't overlap, the
sticky header/controls stack cleanly, the chart fills its card, and the
Plotly layout switches to its compact variant below the 640px breakpoint.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.conftest import App
from tests.e2e.openmeteo_mock import OpenMeteoMock

NARROW_BREAKPOINT = 640
# WCAG 2.2 SC 2.5.8 (AA) minimum target size.
MIN_TARGET_PX = 24

VIEWPORTS: dict[str, dict[str, Any]] = {
    "phone-small-320": {"viewport": {"width": 320, "height": 568}, "touch": True},
    "phone-375": {"viewport": {"width": 375, "height": 667}, "touch": True},
    "phone-large-414": {"viewport": {"width": 414, "height": 896}, "touch": True},
    "tablet-portrait-768": {"viewport": {"width": 768, "height": 1024}, "touch": True},
    "tablet-landscape-1024": {"viewport": {"width": 1024, "height": 768}, "touch": True},
    "laptop-1366": {"viewport": {"width": 1366, "height": 768}, "touch": False},
    "desktop-1920": {"viewport": {"width": 1920, "height": 1080}, "touch": False},
}


@pytest.fixture(params=list(VIEWPORTS), ids=list(VIEWPORTS))
def screen(request: pytest.FixtureRequest, make_app: Callable[..., App]) -> App:
    spec = VIEWPORTS[request.param]
    return make_app(
        viewport=spec["viewport"],
        has_touch=spec["touch"],
        is_mobile=spec["touch"] and spec["viewport"]["width"] < NARROW_BREAKPOINT,
    ).open()


def _box(page: Page, selector: str) -> dict[str, float]:
    box = page.locator(selector).first.bounding_box()
    assert box is not None, f"{selector} is not rendered"
    return box


def _overlap(a: dict[str, float], b: dict[str, float]) -> bool:
    return not (
        a["x"] + a["width"] <= b["x"]
        or b["x"] + b["width"] <= a["x"]
        or a["y"] + a["height"] <= b["y"]
        or b["y"] + b["height"] <= a["y"]
    )


def _width(page: Page) -> int:
    return page.viewport_size["width"]  # type: ignore[index]


# ---- Page-level layout ----------------------------------------------------


def test_no_horizontal_scroll(screen: App) -> None:
    page = screen.page
    scroll_w, client_w = page.evaluate(
        "() => [document.documentElement.scrollWidth, document.documentElement.clientWidth]"
    )
    assert scroll_w <= client_w, f"page is {scroll_w - client_w}px wider than the viewport"


@pytest.mark.parametrize(
    "selector",
    [
        ".app-header",
        "h1.brand",
        "#theme-select",
        ".controls",
        "#location-input",
        "#range-select",
        ".chart-wrap",
        "#kpis",
        ".app-footer",
    ],
)
def test_element_fits_inside_viewport(screen: App, selector: str) -> None:
    box = _box(screen.page, selector)
    vw = _width(screen.page)
    assert box["x"] >= 0, f"{selector} starts {-box['x']:.0f}px off-screen"
    assert box["x"] + box["width"] <= vw + 0.5, (
        f"{selector} overflows the {vw}px viewport by {box['x'] + box['width'] - vw:.0f}px"
    )


def test_header_and_controls_do_not_overlap(screen: App) -> None:
    page = screen.page
    assert not _overlap(_box(page, "h1.brand"), _box(page, "#theme-select"))
    assert not _overlap(_box(page, "#location-input"), _box(page, "#range-select"))


def test_sticky_controls_sit_flush_under_header_when_scrolled(screen: App) -> None:
    page = screen.page
    if page.evaluate("() => document.documentElement.scrollHeight > innerHeight"):
        page.mouse.wheel(0, 2000)
        page.wait_for_function("() => window.scrollY > 0")
    header, controls = _box(page, ".app-header"), _box(page, ".controls")
    assert header["y"] == pytest.approx(0, abs=1)
    gap = controls["y"] - (header["y"] + header["height"])
    assert gap == pytest.approx(0, abs=1), (
        f"sticky controls are {gap:+.1f}px from the header's bottom edge "
        "(negative = covered by header, positive = content shows through)"
    )


def test_interactive_targets_meet_minimum_size(screen: App) -> None:
    page = screen.page
    for selector in ("#theme-select", "#location-input", "#range-select"):
        box = _box(page, selector)
        assert box["height"] >= MIN_TARGET_PX, f"{selector} is only {box['height']:.0f}px tall"
        assert box["width"] >= MIN_TARGET_PX, f"{selector} is only {box['width']:.0f}px wide"


def test_kpi_text_is_not_clipped(screen: App) -> None:
    clipped = screen.page.evaluate(
        """() => [...document.querySelectorAll('#kpis .kpi > *')]
            .filter(el => el.scrollWidth > el.clientWidth + 1)
            .map(el => el.textContent)"""
    )
    assert clipped == []


def test_suggestions_dropdown_fits_viewport(screen: App) -> None:
    page = screen.page
    page.locator("#location-input").fill("Lon")
    expect(page.locator("#location-suggestions")).to_be_visible()
    box = _box(page, "#location-suggestions")
    assert box["x"] >= 0
    assert box["x"] + box["width"] <= _width(page) + 0.5
    # Must draw above the chart card, not behind it.
    top = page.evaluate(
        """() => {
            const li = document.querySelector('#location-suggestions li');
            const r = li.getBoundingClientRect();
            return document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2) === li;
        }"""
    )
    assert top, "suggestion list is covered by another element"


def test_error_banner_fits_viewport(screen: App) -> None:
    page = screen.page
    message = (
        "Failed to fetch data: Open-Meteo https://archive-api.open-meteo.com/v1/archive: "
        "500 Internal Server Error"
    )
    page.evaluate(
        """(msg) => {
            document.getElementById('error-banner-text').textContent = msg;
            document.getElementById('error-banner').hidden = false;
        }""",
        message,
    )
    box = _box(page, "#error-banner")
    assert box["width"] <= _width(page) + 0.5
    close = _box(page, "#error-banner-close")
    assert close["x"] + close["width"] <= _width(page) + 0.5, "dismiss button pushed off-screen"


# ---- Chart ----------------------------------------------------------------


def test_chart_fills_its_card(screen: App) -> None:
    page = screen.page
    wrap_inner = page.evaluate(
        """() => {
            const el = document.querySelector('.chart-wrap');
            const cs = getComputedStyle(el);
            return el.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
        }"""
    )
    svg = _box(page, "#chart .main-svg")
    assert svg["width"] <= wrap_inner + 1, "chart is wider than its card"
    assert svg["width"] >= wrap_inner - 2, "chart does not fill its card"
    assert svg["height"] >= 500


def test_chart_title_legend_and_labels_stay_inside_plot(screen: App) -> None:
    page = screen.page
    svg = _box(page, "#chart .main-svg")
    for selector in ("#chart .gtitle", "#chart .legend", "#chart .annotation"):
        for i, el in enumerate(page.locator(selector).all()):
            box = el.bounding_box()
            if box is None or box["width"] == 0:
                continue
            what = f"{selector}[{i}] ({el.text_content()!r})"
            assert box["x"] >= svg["x"] - 1, f"{what} is clipped on the left"
            assert box["x"] + box["width"] <= svg["x"] + svg["width"] + 1, (
                f"{what} is clipped on the right"
            )
            assert box["y"] >= svg["y"] - 1, f"{what} is clipped at the top"
            assert box["y"] + box["height"] <= svg["y"] + svg["height"] + 1, (
                f"{what} is clipped at the bottom"
            )


def _extrema_label_collisions(app: App) -> list[tuple[str, str]]:
    labels = app.page.locator("#chart .annotation").all()
    # Measure the label box (rect.bg) only — the .annotation group also spans its arrow.
    boxes = [(el.text_content(), el.locator("rect.bg").bounding_box()) for el in labels]
    boxes = [
        (t, b) for t, b in boxes if b and b["width"] > 0 and t and t.startswith(("max", "min"))
    ]
    return [
        (a, b) for i, (a, ba) in enumerate(boxes) for b, bb in boxes[i + 1 :] if _overlap(ba, bb)
    ]


def test_chart_max_min_labels_do_not_collide(screen: App) -> None:
    assert _extrema_label_collisions(screen) == []


@pytest.mark.parametrize("width", [320, 1366])
def test_labels_do_not_collide_when_peaks_coincide(
    make_app: Callable[..., App], mock: OpenMeteoMock, width: int
) -> None:
    # Worst case: temperature and humidity peak at the very same hour.
    mock.humidity_phase = 1.0
    app = make_app(viewport={"width": width, "height": 800}).open()
    assert _extrema_label_collisions(app) == []


def test_chart_uses_compact_layout_below_breakpoint(screen: App) -> None:
    layout = screen.layout()
    names = [t["name"] for t in screen.traces()]
    if _width(screen.page) < NARROW_BREAKPOINT:
        assert layout["legend"]["y"] < 0, "legend should move below the plot on phones"
        assert "Temp" in names
    else:
        assert layout["legend"]["y"] > 1, "legend should sit above the plot"
        assert "Temperature (°C)" in names


def test_modebar_hidden_on_touch_devices(screen: App) -> None:
    page = screen.page
    has_hover = page.evaluate("() => matchMedia('(hover: hover)').matches")
    modebar = page.locator("#chart .modebar")
    if has_hover:
        expect(modebar).to_have_count(1)
    else:
        expect(modebar).to_have_count(0)


# ---- Resizing ---------------------------------------------------------------


def test_rotating_across_breakpoint_rerenders_chart(make_app: Callable[..., App]) -> None:
    app = make_app(viewport={"width": 1024, "height": 600}).open()
    page = app.page
    assert app.layout()["legend"]["y"] > 1

    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_function("() => document.getElementById('chart').layout.legend.y < 0")
    svg = _box(page, "#chart .main-svg")
    assert svg["width"] <= 390

    page.set_viewport_size({"width": 1024, "height": 600})
    page.wait_for_function("() => document.getElementById('chart').layout.legend.y > 1")


def test_dark_theme_on_phone(make_app: Callable[..., App]) -> None:
    app = make_app(
        viewport={"width": 375, "height": 667},
        has_touch=True,
        is_mobile=True,
        color_scheme="dark",
    ).open()
    expect(app.page.locator("html")).to_have_attribute("data-theme", "dark")
    assert app.layout()["paper_bgcolor"] == "#1a1a19"
    scroll_w, client_w = app.page.evaluate(
        "() => [document.documentElement.scrollWidth, document.documentElement.clientWidth]"
    )
    assert scroll_w <= client_w
