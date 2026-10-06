"""Design-system checks: token contrast, CSS ↔ chart palette sync, touch/iOS
ergonomics, reduced motion and first-paint theming."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.conftest import PREFS_KEY, App

THEMES = ["light", "dark"]


def _luminance(hex_color: str) -> float:
    h = hex_color.strip().lstrip("#")
    channels = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contrast(a: str, b: str) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _tokens(page: Page, *names: str) -> dict[str, str]:
    return page.evaluate(
        """(names) => {
            const cs = getComputedStyle(document.documentElement);
            return Object.fromEntries(names.map(n => [n, cs.getPropertyValue(n).trim()]));
        }""",
        list(names),
    )


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("ink", ["--text", "--text-2", "--text-mute", "--accent"])
@pytest.mark.parametrize("ground", ["--surface", "--page"])
def test_text_tokens_meet_wcag_aa(app: App, theme: str, ink: str, ground: str) -> None:
    app.open(f"?theme={theme}")
    t = _tokens(app.page, ink, ground)
    ratio = _contrast(t[ink], t[ground])
    assert ratio >= 4.5, f"{theme}: {ink} {t[ink]} on {ground} {t[ground]} is {ratio:.2f}:1"


@pytest.mark.parametrize("theme", THEMES)
def test_css_tokens_match_chart_palette(app: App, theme: str) -> None:
    app.open(f"?theme={theme}")
    t = _tokens(app.page, "--surface", "--series-temp", "--series-humidity")
    palette = app.page.evaluate(
        "async (theme) => (await import('/theme.js')).paletteFor(theme)", theme
    )
    assert palette["paperBg"] == t["--surface"]
    assert palette["tempLine"] == t["--series-temp"]
    assert palette["humidityLine"] == t["--series-humidity"]


def test_inputs_use_16px_text_on_phones(make_app: Callable[..., App]) -> None:
    # iOS Safari zooms the page when focusing an input whose font is < 16px.
    app = make_app(viewport={"width": 375, "height": 667}, has_touch=True, is_mobile=True)
    page = app.open().page
    for selector in ("#location-input", "#range-select", "#theme-select"):
        expect(page.locator(selector)).to_have_css("font-size", "16px")


def test_touch_targets_grow_on_coarse_pointers(make_app: Callable[..., App]) -> None:
    app = make_app(viewport={"width": 768, "height": 1024}, has_touch=True, is_mobile=True)
    page = app.open().page
    assert page.evaluate("() => matchMedia('(pointer: coarse)').matches")
    for selector in ("#location-input", "#range-select", "#theme-select"):
        box = page.locator(selector).bounding_box()
        assert box is not None
        assert box["height"] >= 40, f"{selector} is {box['height']:.0f}px tall"


def test_reduced_motion_stops_decorative_animation(make_app: Callable[..., App]) -> None:
    app = make_app(reduced_motion="reduce").open()
    duration = app.page.evaluate(
        "() => parseFloat(getComputedStyle(document.querySelector('.heart')).animationDuration)"
    )
    assert duration < 0.001


@pytest.mark.parametrize(
    ("saved", "query", "color_scheme", "expected"),
    [
        ("dark", "", "light", "dark"),
        ("light", "", "dark", "light"),
        ("system", "", "dark", "dark"),
        ("light", "?theme=dark", "light", "dark"),
    ],
)
def test_theme_applied_before_app_script_runs(
    make_app: Callable[..., App], saved: str, query: str, color_scheme: str, expected: str
) -> None:
    app = make_app(color_scheme=color_scheme)
    page = app.page
    page.add_init_script(
        f"localStorage.setItem('{PREFS_KEY}', JSON.stringify({{theme: '{saved}'}}))"
    )
    # Block the app bundle: only the inline <head> script can set the theme.
    page.route("**/app.js", lambda route: route.abort())
    page.goto(f"/{query}")
    expect(page.locator("html")).to_have_attribute("data-theme", expected)
