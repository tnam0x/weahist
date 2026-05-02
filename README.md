# Weather History

A small web app to explore the recent **weather** and **air-quality** history of any place on Earth.

Type a city, pick a time range, and get an interactive chart that shows what the weather and the air were really like — no sign-up, no API key, no setup.

## What it shows

For any location you choose:

- **Temperature** over time, with the daily max and min highlighted.
- **Relative humidity** plotted on the same panel as a second line.
- **Air Quality Index** (US AQI) with the official EPA color bands behind the line — Good, Moderate, Unhealthy for Sensitive Groups, Unhealthy, Very Unhealthy, Hazardous.
- The **max and min AQI** of the period, each labeled with its category.
- A small summary card with the granularity (hourly / daily), number of observations, peak/min temperature, peak AQI, and how much of the requested period actually has AQI data.

Weekends are gently shaded and day boundaries are marked, so it's easy to read at a glance.

## What you can do

- **Search any city in the world** with a free-text box that suggests matches as you type.
- **Pick a time range** from quick presets:
  - Last 24 hours
  - Last 3 days
  - Last 7 days *(default)*
  - Last 2 weeks
  - Last 30 days
  - Last 3 months
  - Last 6 months
  - Last 1 year

  Long ranges automatically switch to a daily view so the chart stays readable.
- **Choose a theme**: 🖥 System (follows your OS), ☀ Light, or 🌙 Dark. The chart re-styles itself to match.
- **Your settings are remembered** — last location, range, and theme are restored next time you open the page.
- **Share a view**: append `?location=…&range=…&theme=…` to the URL and the page will load with those settings.

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

If you'd rather run it locally (with the optional Python backend for development), the same `web/` is also served by the FastAPI app:

```bash
uv run uvicorn weahist.api.app:app --reload
# open http://127.0.0.1:8000
```

## Author

Made with ❤️ by **tnam0x** · [namtran4194@gmail.com](mailto:namtran4194@gmail.com)
