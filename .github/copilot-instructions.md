# Weather History (`weahist`) — Project Rules

A pure-static web app that charts historical weather and air-quality data for any city.
The browser calls Open-Meteo directly; there is no backend.

## Stack
- `web/`: plain HTML, CSS and ES modules — no framework, no bundler, no build step for the app.
- Charts: Plotly **basic** bundle from the CDN (`plotly-basic-<version>.min.js`, loaded with `defer`).
  Only use trace types included in that bundle (scatter, bar, pie).
- Hosting: GitHub Pages, deployed by `.github/workflows/pages.yml` after the tests pass.
- Tooling: Python 3.11+ with `uv`, only for the test suite (pytest + pytest-playwright, ruff).

## Layout
```
web/
  index.html   # shell, SEO/OG metadata, JSON-LD
  styles.css   # design tokens (light/dark chosen separately) + layout
  app.js       # state, prefs, controls, rendering
  api.js       # Open-Meteo client, range resolution, response cache
  chart.js     # one Plotly figure per card (single y-axis each)
  aqi.js       # US EPA AQI bands and advice
  theme.js     # chart palettes mirroring the CSS tokens
tests/e2e/     # Playwright tests with a deterministic Open-Meteo mock
```

## Data source
Open-Meteo only (no API keys): geocoding, archive + forecast weather, air quality.
AQI history may be shorter than the requested range — degrade gracefully, never fail the page.
Times are shown in the location's timezone.

## Conventions
- Build DOM with `textContent`/`createElement`; never put API or user data into `innerHTML`
  without escaping.
- Text uses ink tokens, never series colors; keep text contrast >= 4.5:1 in both themes.
- One y-axis per chart; label extrema selectively; every chart has a table view.
- Keep `theme.js` in sync with the CSS tokens (a test enforces it).

## Testing
- Every upstream call is mocked (`tests/e2e/openmeteo_mock.py`); tests must not hit the network.
- The browser clock is pinned (`FIXED_NOW`) so dates and counts are deterministic.
- New UI behaviour needs an e2e test; layout changes should keep `test_responsive.py` green
  on all viewports.
