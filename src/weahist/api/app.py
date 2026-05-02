"""FastAPI app — JSON history endpoint, Plotly figure JSON, and SPA shell."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Annotated, Any, Literal

import plotly.io as pio
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from weahist.api.deps import get_service
from weahist.errors import GeocodingError, UpstreamError, WeahistError
from weahist.models import Granularity
from weahist.services.history import WeatherHistoryService
from weahist.visualization.plotly_renderer import PlotlyRenderer, Theme

app = FastAPI(title="Weather History", version="0.1.0")

# Serve the pure-static frontend in `web/` at /. The same folder is also
# deployed to GitHub Pages — single source of truth.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_WEB_DIR = _REPO_ROOT / "web"


# ---------------------------------------------------------------------------
# Range presets (relative to "today")
# ---------------------------------------------------------------------------

_RangeKey = Literal["1d", "3d", "1w", "2w", "1m", "3m", "6m", "1y"]
_RANGE_DAYS: dict[str, int] = {
    "1d": 1,
    "3d": 3,
    "1w": 7,
    "2w": 14,
    "1m": 30,
    "3m": 90,
    "6m": 180,
    "1y": 365,
}


def _resolve_range(range_key: str | None) -> tuple[date, date, Granularity]:
    """Translate a preset key into ``(start, end, auto-granularity)``."""
    key = (range_key or "1w").lower()
    if key not in _RANGE_DAYS:
        raise HTTPException(status_code=400, detail=f"unknown range: {key}")
    days = _RANGE_DAYS[key]
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=days - 1)
    granularity: Granularity = "daily" if days > 30 else "hourly"
    return start, end, granularity


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# JSON API
# ---------------------------------------------------------------------------


@app.get("/api/locations")
def api_locations(
    q: Annotated[str, Query(min_length=1, max_length=80, description="Search text.")],
    service: Annotated[WeatherHistoryService, Depends(get_service)],
    limit: Annotated[int, Query(ge=1, le=10)] = 5,
) -> dict[str, Any]:
    """Typeahead suggestions backed by Open-Meteo geocoding."""
    try:
        data = service._http.get_json(  # noqa: SLF001
            service._geocoder._settings.geocoding_url,  # noqa: SLF001
            {"name": q, "count": limit, "format": "json", "language": "en"},
        )
    except UpstreamError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    results = data.get("results") or []
    out = [
        {
            "name": r.get("name"),
            "country": r.get("country"),
            "admin1": r.get("admin1"),
            "latitude": r.get("latitude"),
            "longitude": r.get("longitude"),
            "timezone": r.get("timezone"),
            "label": ", ".join(
                str(v) for v in (r.get("name"), r.get("admin1"), r.get("country")) if v
            ),
        }
        for r in results
    ]
    return {"results": out}


def _fetch(
    service: WeatherHistoryService, location: str, range_key: str | None
) -> tuple[Any, Any, Granularity]:
    start, end, gran = _resolve_range(range_key)
    try:
        query, df = service.get_history(location, start=start, end=end, granularity=gran)
    except GeocodingError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except UpstreamError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except WeahistError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return query, df, gran


@app.get("/api/history")
def api_history(
    location: Annotated[str, Query(description="City name, e.g. 'Hanoi, Vietnam'.")],
    service: Annotated[WeatherHistoryService, Depends(get_service)],
    range: Annotated[str, Query(alias="range")] = "1w",
) -> dict[str, Any]:
    query, df, granularity = _fetch(service, location, range)
    aqi_coverage = (
        float(df["us_aqi"].notna().mean()) if "us_aqi" in df.columns and not df.empty else 0.0
    )
    records = df.reset_index().to_dict(orient="records")
    for r in records:
        if r.get("time") is not None:
            r["time"] = r["time"].isoformat()
    return {
        "location": query.location.model_dump(),
        "start": query.start.isoformat(),
        "end": query.end.isoformat(),
        "granularity": granularity,
        "aqi_coverage": aqi_coverage,
        "row_count": len(records),
        "rows": records,
    }


@app.get("/api/plot.json")
def api_plot_json(
    location: Annotated[str, Query()],
    service: Annotated[WeatherHistoryService, Depends(get_service)],
    range: Annotated[str, Query(alias="range")] = "1w",
    theme: Annotated[Theme, Query()] = "light",
) -> JSONResponse:
    query, df, _gran = _fetch(service, location, range)
    fig = PlotlyRenderer(theme=theme).build_figure(df, query)
    return JSONResponse(content={"figure": pio.to_json(fig, validate=False)})


# ---------------------------------------------------------------------------
# Legacy endpoints (kept for backward compatibility)
# ---------------------------------------------------------------------------


@app.get("/history")
def history_legacy(
    location: Annotated[str, Query()],
    start: date,
    end: date,
    service: Annotated[WeatherHistoryService, Depends(get_service)],
    granularity: Granularity = "hourly",
) -> dict[str, Any]:
    try:
        query, df = service.get_history(location, start=start, end=end, granularity=granularity)
    except GeocodingError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except UpstreamError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except WeahistError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    records = df.reset_index().to_dict(orient="records")
    for r in records:
        if r.get("time") is not None:
            r["time"] = r["time"].isoformat()
    return {
        "location": query.location.model_dump(),
        "start": query.start.isoformat(),
        "end": query.end.isoformat(),
        "granularity": query.granularity,
        "rows": records,
    }


@app.get("/plot.html", response_class=HTMLResponse)
def plot_html(
    location: Annotated[str, Query()],
    start: date,
    end: date,
    service: Annotated[WeatherHistoryService, Depends(get_service)],
    granularity: Granularity = "hourly",
    theme: Theme = "light",
) -> HTMLResponse:
    try:
        query, df = service.get_history(location, start=start, end=end, granularity=granularity)
    except GeocodingError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except UpstreamError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    fig = PlotlyRenderer(theme=theme).build_figure(df, query)
    return HTMLResponse(content=fig.to_html(include_plotlyjs="cdn"))


# Mount the SPA assets last so /api/* and other explicit routes win.
if _WEB_DIR.is_dir():
    app.mount("/", StaticFiles(directory=_WEB_DIR, html=True), name="web")
