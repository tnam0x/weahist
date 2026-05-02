"""Typer CLI adapter — thin wrapper around `WeatherHistoryService`."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Annotated

import typer

from weahist.models import Granularity
from weahist.services.history import WeatherHistoryService
from weahist.visualization.base import Renderer
from weahist.visualization.matplotlib_renderer import MatplotlibRenderer
from weahist.visualization.plotly_renderer import PlotlyRenderer

app = typer.Typer(help="Fetch and visualize historical weather + AQI from Open-Meteo.")
logger = logging.getLogger(__name__)


def _default_start() -> date:
    return date.today() - timedelta(days=30)


def _default_end() -> date:
    return date.today() - timedelta(days=1)


def _renderer_for(name: str) -> Renderer:
    if name == "matplotlib":
        return MatplotlibRenderer()
    if name == "plotly":
        return PlotlyRenderer()
    raise typer.BadParameter(f"unknown renderer {name!r} (choose: matplotlib, plotly)")


@app.callback()
def _setup(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )


@app.command()
def fetch(
    location: Annotated[str, typer.Argument(help="City name, e.g. 'Hanoi, Vietnam'.")],
    start: Annotated[datetime | None, typer.Option(formats=["%Y-%m-%d"])] = None,
    end: Annotated[datetime | None, typer.Option(formats=["%Y-%m-%d"])] = None,
    granularity: Annotated[Granularity, typer.Option()] = "hourly",
    no_cache: Annotated[bool, typer.Option("--no-cache")] = False,
) -> None:
    """Fetch weather + AQI history and print a summary."""
    start_d: date = start.date() if start else _default_start()
    end_d: date = end.date() if end else _default_end()
    service = WeatherHistoryService()
    query, df = service.get_history(
        location, start=start_d, end=end_d, granularity=granularity, use_cache=not no_cache
    )
    typer.echo(
        f"Location: {query.location.name} ({query.location.latitude:.3f},"
        f" {query.location.longitude:.3f}, tz={query.location.timezone})"
    )
    typer.echo(f"Range:    {query.start} → {query.end}  ({query.granularity})")
    typer.echo(f"Rows:     {len(df)}")
    typer.echo(f"Columns:  {', '.join(df.columns)}")
    if "us_aqi" in df.columns:
        coverage = df["us_aqi"].notna().mean() * 100 if len(df) else 0.0
        typer.echo(f"AQI cov:  {coverage:.1f}% ({df['us_aqi'].notna().sum()} rows)")
    else:
        typer.echo("AQI cov:  unavailable for this range")


@app.command()
def plot(
    location: Annotated[str, typer.Argument(help="City name.")],
    start: Annotated[datetime | None, typer.Option(formats=["%Y-%m-%d"])] = None,
    end: Annotated[datetime | None, typer.Option(formats=["%Y-%m-%d"])] = None,
    granularity: Annotated[Granularity, typer.Option()] = "hourly",
    renderer: Annotated[str, typer.Option(help="matplotlib | plotly")] = "plotly",
    out: Annotated[Path | None, typer.Option(help="Output path (auto-named if omitted).")] = None,
) -> None:
    """Fetch and render a chart to PNG (matplotlib) or HTML (plotly)."""
    start_d: date = start.date() if start else _default_start()
    end_d: date = end.date() if end else _default_end()
    rndr = _renderer_for(renderer)
    service = WeatherHistoryService()
    query, df = service.get_history(location, start=start_d, end=end_d, granularity=granularity)

    output = out or Path(
        f"weahist_{query.location.name.replace(' ', '_')}"
        f"_{start_d.isoformat()}_{end_d.isoformat()}{rndr.extension}"
    )
    written = rndr.render(df, query, output)
    typer.echo(f"Wrote {written}")


if __name__ == "__main__":
    app()
