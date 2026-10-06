"""Chart cards: daily bands, AQI legend, synced crosshair/zoom, table view and
refetch behaviour."""

from __future__ import annotations

from playwright.sync_api import expect

from tests.e2e.conftest import App


def test_daily_cards_draw_low_high_band_under_mean(app: App) -> None:
    app.open("?range=3m")
    for chart in ("temperature", "humidity"):
        assert [t["name"] for t in app.traces(chart)] == ["High", "Low", "Mean"]
        fills = app.page.evaluate(
            "(id) => document.getElementById(id).data.map(t => t.fill || null)",
            f"chart-{chart}",
        )
        assert fills == [None, "tonexty", None]
    expect(app.page.locator('[data-chart="temperature"] .card-sub')).to_have_text(
        "°C · daily low–high range and mean"
    )


def test_hourly_view_shades_weekends(app: App) -> None:
    app.open()  # Mar 9–15, 2026: Sat 14th and Sun 15th
    rects = [s for s in app.layout()["shapes"] if s["type"] == "rect" and s["yref"] == "y domain"]
    assert [(r["x0"][:10], r["x1"][:10]) for r in rects] == [
        ("2026-03-14", "2026-03-15"),
        ("2026-03-15", "2026-03-16"),
    ]


def test_aqi_card_lists_visible_bands(app: App) -> None:
    app.open()
    legend = app.page.locator('[data-chart="aqi"] .band-legend li')
    expect(legend).to_have_text(["Good", "Moderate"])


def test_hovering_one_card_shows_crosshair_in_the_others(app: App) -> None:
    app.open()
    page = app.page
    box = page.locator("#chart-temperature .nsewdrag").bounding_box()
    assert box is not None
    page.mouse.move(box["x"] + box["width"] * 0.4, box["y"] + box["height"] / 2)
    for chart in ("temperature", "humidity", "aqi"):
        expect(page.locator(f"#chart-{chart} .hoverlayer .legend")).to_have_count(1)

    page.mouse.move(box["x"] + box["width"] / 2, box["y"] - 200)  # leave the plot
    for chart in ("humidity", "aqi"):
        expect(page.locator(f"#chart-{chart} .hoverlayer .legend")).to_have_count(0)


def test_zooming_one_card_zooms_the_others(app: App) -> None:
    app.open()
    page = app.page
    drag = page.locator("#chart-humidity .nsewdrag")
    drag.scroll_into_view_if_needed()
    box = drag.bounding_box()
    assert box is not None
    y = box["y"] + box["height"] / 2
    page.mouse.move(box["x"] + box["width"] * 0.2, y)
    page.mouse.down()
    page.mouse.move(box["x"] + box["width"] * 0.5, y, steps=5)
    page.mouse.up()

    page.wait_for_function(
        "() => !document.getElementById('chart-temperature').layout.xaxis.autorange"
    )
    ranges = {
        chart: app.layout(chart)["xaxis"]["range"] for chart in ("temperature", "humidity", "aqi")
    }
    assert ranges["temperature"] == ranges["humidity"] == ranges["aqi"]

    page.mouse.dblclick(box["x"] + box["width"] / 2, y)  # reset
    page.wait_for_function(
        "() => document.getElementById('chart-aqi').layout.xaxis.autorange === true"
    )


def test_table_view_toggles_with_the_chart(app: App) -> None:
    app.open()
    card = app.page.locator('[data-chart="temperature"]')
    toggle = card.locator('[data-action="table"]')

    toggle.click()
    expect(toggle).to_have_attribute("aria-pressed", "true")
    expect(toggle).to_have_text("Chart")
    expect(card.locator(".chart-wrap")).to_be_hidden()
    table = card.locator("table.data-table")
    expect(table.locator("thead th")).to_have_text(["Time", "Temperature (°C)"])
    expect(table.locator("tbody tr")).to_have_count(168)
    expect(table.locator("tbody tr").first.locator("td")).to_have_text(["2026-03-09 00:00", "25.0"])

    toggle.click()
    expect(toggle).to_have_attribute("aria-pressed", "false")
    expect(card.locator(".table-wrap")).to_be_hidden()
    expect(card.locator(".chart-wrap")).to_be_visible()
    assert (card.locator(".main-svg").first.bounding_box() or {}).get("width", 0) > 200


def test_table_view_survives_range_change_and_shows_daily_columns(app: App) -> None:
    app.open()
    card = app.page.locator('[data-chart="aqi"]')
    card.locator('[data-action="table"]').click()
    expect(card.locator("thead th")).to_have_text(
        ["Time", "US AQI", "PM2.5 (µg/m³)", "PM10 (µg/m³)"]
    )

    app.page.select_option("#range-select", "3m")
    expect(card.locator("thead th").first).to_have_text("Date")
    expect(card.locator("tbody tr")).to_have_count(90)


def test_refetch_keeps_previous_render_dimmed(app: App) -> None:
    app.open()
    page = app.page
    height = page.evaluate("() => document.documentElement.scrollHeight")

    app.mock.hold = True
    page.select_option("#range-select", "2w")
    expect(page.locator("body")).to_have_class("is-loading")
    expect(page.locator("#loading")).to_be_visible()
    expect(page.locator("#status")).to_be_hidden()
    expect(page.locator("#kpis")).to_be_visible()
    expect(page.locator("#charts")).to_have_css("opacity", "0.5")
    assert page.evaluate("() => document.documentElement.scrollHeight") == height

    app.mock.release()
    expect(page.locator("#kpis")).to_contain_text(f"{14 * 24} hourly readings")
    expect(page.locator("#charts")).to_have_css("opacity", "1")
