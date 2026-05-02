"""Plotly renderer (interactive HTML)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from weahist.errors import RenderError
from weahist.models import HistoryQuery
from weahist.visualization._helpers import (
    AQI_BANDS,
    aqi_category,
    aqi_max,
    build_title,
    day_boundaries,
    temp_column,
    to_local,
    weekend_spans,
)

Theme = Literal["light", "dark"]


@dataclass(frozen=True)
class ThemePalette:
    template: str
    paper_bg: str
    plot_bg: str
    text: str
    text_mute: str
    grid: str
    border: str
    temp_line: str
    humidity_line: str
    aqi_line: str
    weekend_fill: str
    day_separator: str
    legend_bg: str
    annotation_bg: str
    band_opacity: tuple[float, ...]  # per AQI_BANDS index


_LIGHT = ThemePalette(
    template="plotly_white",
    paper_bg="#FFFFFF",
    plot_bg="#FFFFFF",
    text="#1F2328",
    text_mute="rgba(0,0,0,0.65)",
    grid="rgba(0,0,0,0.08)",
    border="rgba(0,0,0,0.4)",
    temp_line="#C0392B",
    humidity_line="#2F80ED",
    aqi_line="#1F2328",
    weekend_fill="rgba(0,0,0,0.06)",
    day_separator="rgba(0,0,0,0.12)",
    legend_bg="rgba(255,255,255,0.7)",
    annotation_bg="rgba(255,255,255,0.85)",
    band_opacity=(0.28, 0.28, 0.28, 0.28, 0.32, 0.40),
)

_DARK = ThemePalette(
    template="plotly_dark",
    paper_bg="#161B22",
    plot_bg="#0D1117",
    text="#E6EDF3",
    text_mute="rgba(230,237,243,0.75)",
    grid="rgba(255,255,255,0.08)",
    border="rgba(230,237,243,0.45)",
    temp_line="#FF6B6B",
    humidity_line="#79C0FF",
    aqi_line="#E6EDF3",
    weekend_fill="rgba(255,255,255,0.05)",
    day_separator="rgba(255,255,255,0.12)",
    legend_bg="rgba(22,27,34,0.75)",
    annotation_bg="rgba(22,27,34,0.85)",
    band_opacity=(0.22, 0.18, 0.25, 0.30, 0.38, 0.50),
)


def _palette(theme: Theme) -> ThemePalette:
    return _DARK if theme == "dark" else _LIGHT


class PlotlyRenderer:
    extension = ".html"

    def __init__(self, theme: Theme = "light") -> None:
        self.theme: Theme = theme

    def build_figure(
        self, df: pd.DataFrame, query: HistoryQuery, theme: Theme | None = None
    ) -> go.Figure:
        return self._build(df, query, _palette(theme or self.theme))

    def render(self, df: pd.DataFrame, query: HistoryQuery, output: Path) -> Path:
        output.parent.mkdir(parents=True, exist_ok=True)
        fig = self.build_figure(df, query)
        fig.write_html(str(output), include_plotlyjs="cdn")
        return output

    def _build(self, df: pd.DataFrame, query: HistoryQuery, p: ThemePalette) -> go.Figure:
        if df.empty:
            raise RenderError("cannot render empty DataFrame")

        local = to_local(df, query.location.timezone)

        temp_col = temp_column(local)
        humid_col = "relative_humidity_2m" if "relative_humidity_2m" in local.columns else None
        has_aqi = "us_aqi" in local.columns and local["us_aqi"].notna().any()

        rows = 2 if has_aqi else 1
        fig = make_subplots(
            rows=rows,
            cols=1,
            shared_xaxes=True,
            row_heights=[0.6, 0.4] if has_aqi else [1.0],
            vertical_spacing=0.08,
            specs=[[{"secondary_y": True}]] + ([[{"secondary_y": False}]] if has_aqi else []),
        )

        idx: pd.DatetimeIndex = local.index  # type: ignore[assignment]
        spans = weekend_spans(idx)
        boundaries = day_boundaries(idx)
        for r in range(1, rows + 1):
            for ws_start, ws_end in spans:
                fig.add_vrect(
                    x0=ws_start,
                    x1=ws_end,
                    fillcolor=p.weekend_fill,
                    opacity=1.0,
                    layer="below",
                    line_width=0,
                    row=r,
                    col=1,
                )
            for boundary in boundaries[1:-1]:
                fig.add_vline(
                    x=boundary,
                    line={"color": p.day_separator, "width": 1, "dash": "dot"},
                    row=r,
                    col=1,
                )

        if temp_col is not None:
            fig.add_scatter(
                x=local.index,
                y=local[temp_col],
                name="Temperature (°C)",
                line={"color": p.temp_line, "width": 2},
                row=1,
                col=1,
                secondary_y=False,
                hovertemplate="<b>%{y:.1f} °C</b><extra>Temperature</extra>",
            )
            self._annotate_extrema(fig, local[temp_col], p, unit="°C")
        if humid_col is not None:
            fig.add_scatter(
                x=local.index,
                y=local[humid_col],
                name="Relative humidity (%)",
                line={"color": p.humidity_line, "width": 1.5},
                row=1,
                col=1,
                secondary_y=True,
                hovertemplate="<b>%{y:.0f}%%</b><extra>Humidity</extra>",
            )
            self._annotate_extrema(
                fig,
                local[humid_col],
                p,
                unit="%",
                secondary_y=True,
                value_fmt=".0f",
                colors=(p.humidity_line, p.humidity_line),
                offsets=(-22, 22),
            )

        if has_aqi:
            top = aqi_max(local)
            aqi_yref = "y3"
            aqi_xref = "x2 domain"
            for i, band in enumerate(AQI_BANDS):
                if band.lower > top:
                    continue
                upper = min(band.upper, top)
                fig.add_shape(
                    type="rect",
                    xref=aqi_xref,
                    yref=aqi_yref,
                    x0=0,
                    x1=1,
                    y0=band.lower,
                    y1=upper,
                    fillcolor=band.color,
                    opacity=p.band_opacity[i],
                    line_width=0,
                    layer="below",
                )
                fig.add_annotation(
                    xref=aqi_xref,
                    yref=aqi_yref,
                    x=0.005,
                    y=(band.lower + upper) / 2,
                    text=band.label,
                    showarrow=False,
                    xanchor="left",
                    yanchor="middle",
                    font={"size": 10, "color": p.text_mute},
                )
            categories = [aqi_category(v) for v in local["us_aqi"].fillna(-1)]
            fig.add_scatter(
                x=local.index,
                y=local["us_aqi"],
                name="AQI",
                mode="lines",
                line={"color": p.aqi_line, "width": 2},
                customdata=categories,
                hovertemplate="<b>AQI %{y:.0f}</b> · %{customdata}<extra></extra>",
                row=2,
                col=1,
            )
            self._annotate_aqi_max(fig, local["us_aqi"], p)
            fig.update_yaxes(
                title_text="AQI (0–500)", range=[0, top], row=2, col=1
            )
            fig.update_xaxes(
                title_text=f"Time ({query.location.timezone})", row=2, col=1
            )
        else:
            fig.update_xaxes(title_text=f"Time ({query.location.timezone})", row=1, col=1)

        fig.update_yaxes(title_text="Temperature (°C)", row=1, col=1, secondary_y=False)
        fig.update_yaxes(title_text="Humidity (%)", row=1, col=1, secondary_y=True)

        fig.update_xaxes(
            showline=True,
            linewidth=1,
            linecolor=p.border,
            mirror=True,
            gridcolor=p.grid,
        )
        fig.update_yaxes(
            showline=True,
            linewidth=1,
            linecolor=p.border,
            mirror=True,
            gridcolor=p.grid,
        )

        title, subtitle = build_title(
            query.location, query.start, query.end, query.granularity, len(df)
        )
        fig.update_layout(
            title={
                "text": f"{title}<br><sub>{subtitle}</sub>",
                "x": 0.02,
                "xanchor": "left",
                "y": 0.97,
                "yanchor": "top",
                "font": {"color": p.text},
            },
            template=p.template,
            paper_bgcolor=p.paper_bg,
            plot_bgcolor=p.plot_bg,
            font={"color": p.text},
            hovermode="x unified",
            margin={"t": 130, "r": 30, "b": 60},
            legend={
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.04,
                "xanchor": "right",
                "x": 1.0,
                "bgcolor": p.legend_bg,
                "bordercolor": p.border,
                "borderwidth": 1,
                "font": {"color": p.text},
            },
        )
        return fig

    @staticmethod
    def _annotate_extrema(
        fig: Any,
        series: pd.Series,
        p: ThemePalette,
        *,
        unit: str,
        secondary_y: bool = False,
        value_fmt: str = ".1f",
        colors: tuple[str, str] | None = None,
        offsets: tuple[int, int] = (-28, 28),
    ) -> None:
        clean = series.dropna()
        if clean.empty:
            return
        max_color, min_color = colors if colors is not None else (p.temp_line, p.temp_line)
        for label, idx, color, ay in (
            ("max", clean.idxmax(), max_color, offsets[0]),
            ("min", clean.idxmin(), min_color, offsets[1]),
        ):
            value = float(clean.loc[idx])
            fig.add_annotation(
                x=idx,
                y=value,
                text=f"{label} {value:{value_fmt}}{unit}",
                showarrow=True,
                arrowhead=2,
                arrowcolor=color,
                ax=0,
                ay=ay,
                font={"size": 10, "color": color},
                bgcolor=p.annotation_bg,
                bordercolor=color,
                borderwidth=1,
                row=1,
                col=1,
                secondary_y=secondary_y,
            )

    @staticmethod
    def _annotate_aqi_max(fig: Any, series: pd.Series, p: ThemePalette) -> None:
        clean = series.dropna()
        if clean.empty:
            return
        for label, idx, ay in (
            ("max", clean.idxmax(), -24),
            ("min", clean.idxmin(), 24),
        ):
            value = float(clean.loc[idx])
            category = aqi_category(value)
            fig.add_annotation(
                x=idx,
                y=value,
                text=f"{label} AQI {value:.0f} · {category}",
                showarrow=True,
                arrowhead=2,
                arrowcolor=p.aqi_line,
                ax=0,
                ay=ay,
                font={"size": 10, "color": p.aqi_line},
                bgcolor=p.annotation_bg,
                bordercolor=p.aqi_line,
                borderwidth=1,
                row=2,
                col=1,
            )
