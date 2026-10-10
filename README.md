# Weather History

A small web app to explore the recent **weather** and **air-quality** history of any place on Earth.

Type a city, pick a time range, and get interactive charts that show what the weather and the air were really like — no sign-up, no API key, no setup. Works on phones, tablets and desktops, in light and dark themes.

## What it shows

For any location you choose:

- **Summary tiles**: average temperature and humidity with their low/high, the **peak AQI** with its category and the EPA's health advice, and how much of the period has AQI data.
- **Three aligned chart cards** — temperature, relative humidity and US AQI — each on its own axis and sharing the same time axis:
  - the max and min of each series are labeled;
  - daily views show the **low–high range as a band** with the mean line on top;
  - the AQI card draws the official EPA color bands (Good → Hazardous) behind the line.
- Hovering (or tapping) one chart shows the same moment in all three; zooming one zooms them all.
- Weekends are gently shaded and day boundaries are marked on hourly views.
- Every chart has a **Table** view with the exact numbers.

## What you can do

- **Search any city in the world** with suggestions as you type, or use **📍 my location**.
- **Recent places**: focus the location box to jump back to your last five places.
- **Pick a time range** with one tap — 24h, 3d, 7d *(default)*, 2w, 30d, 3m, 6m, 1y — or a **custom date range** of up to 366 days. Ranges over 30 days switch to a daily view.
- **Switch units** between °C and °F.
- **Choose a theme**: 🖥 System (follows your OS), ☀ Light, or 🌙 Dark.
- **Share** the current view as a link (copied to the clipboard, or the native share sheet on phones).
- **Download** the data as CSV, or any chart as a PNG.
- **Your settings are remembered** — location, range, units and theme are restored next time. Links accept `?location=…&range=…` (or `&start=YYYY-MM-DD&end=YYYY-MM-DD`), `&units=f` and `&theme=dark`.

## Where the data comes from

All data is provided by [Open-Meteo](https://open-meteo.com/), a free open-source weather service that aggregates atmospheric model output (CAMS for air quality, ECMWF/IFS for weather) without requiring an API key.

- Weather: hourly or daily archive going back many years.
- Air quality: typically the last ~2–3 years. If part of your selected range has no AQI data, the chart still shows the weather and the summary tells you the coverage percentage.

## Notes

- Times shown on the chart are in the **local timezone of the selected location**, not your browser's timezone.
- Air-quality numbers use the **US EPA AQI standard** (0–500, six categories). It's a close proxy for most national indices.
- If a request takes more than 30 seconds it is cancelled and a clear error is shown at the top of the page.

## Hosting

The frontend lives in [`web/`](web/) and is **pure static** — HTML, CSS, and a few small ES module JS files. The browser talks to Open-Meteo directly (no backend needed), so it can be hosted anywhere that serves static files.

### Local development

There is no build step for the app itself. Serve `web/` with any static file server:

```bash
python -m http.server -d web 8000     # open http://127.0.0.1:8000
scripts/serve-lan.sh                  # same, reachable from your phone on the LAN
```

### Tests

The app is covered by browser tests in [`tests/e2e/`](tests/e2e/) (pytest-playwright, Chromium).
They serve `web/` statically and mock every Open-Meteo call, so they need no network
after the first run (the pinned Plotly bundle is cached under `.cache/e2e/`).

```bash
uv sync                               # test tooling only — the app has no Python code
uv run playwright install chromium    # once
uv run pytest                         # everything
uv run pytest --headed -k filters     # watch some of them run
```

The suite checks behaviour (search, ranges, units, themes, saved prefs, shareable URLs,
caching, error/timeout handling), layout on phone, tablet and desktop viewports, design
tokens and contrast, and SEO metadata.

GitHub Actions runs lint and the full suite on every push and pull request; `main` is
deployed to GitHub Pages only when the tests pass.

## Author

Made with ❤️ by **tnam0x** · [namtran4194@gmail.com](mailto:namtran4194@gmail.com)
