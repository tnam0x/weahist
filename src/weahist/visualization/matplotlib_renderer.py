"""Matplotlib renderer (static PNG)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # noqa: E402

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

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


class MatplotlibRenderer:
    extension = ".png"

    def render(self, df: pd.DataFrame, query: HistoryQuery, output: Path) -> Path:
        if df.empty:
            raise RenderError("cannot render empty DataFrame")

        output.parent.mkdir(parents=True, exist_ok=True)
        local = to_local(df, query.location.timezone)

        temp_col = temp_column(local)
        humid_col = "relative_humidity_2m" if "relative_humidity_2m" in local.columns else None
        has_aqi = "us_aqi" in local.columns and local["us_aqi"].notna().any()

        if has_aqi:
            fig, (ax_top, ax_aqi) = plt.subplots(
                2,
                1,
                figsize=(11, 6.5),
                sharex=True,
                gridspec_kw={"height_ratios": [3, 2], "hspace": 0.12},
            )
        else:
            fig, ax_top = plt.subplots(figsize=(11, 5))
            ax_aqi = None

        # Weekend shading + day separators on every panel.
        idx: pd.DatetimeIndex = local.index  # type: ignore[assignment]
        spans = weekend_spans(idx)
        boundaries = day_boundaries(idx)
        panels = [ax_top] + ([ax_aqi] if ax_aqi is not None else [])
        for ax in panels:
            for ws_start, ws_end in spans:
                ax.axvspan(ws_start, ws_end, color="lightgray", alpha=0.18, zorder=0)
            for boundary in boundaries[1:-1]:
                ax.axvline(
                    boundary, color="black", alpha=0.12, linestyle=":", linewidth=0.8, zorder=0
                )

        # --- Top panel: temperature + humidity ---
        if temp_col is not None:
            ax_top.plot(
                local.index,
                local[temp_col],
                color="crimson",
                linewidth=1.8,
                label="Temperature (°C)",
            )
            self._annotate_extrema(ax_top, local[temp_col], unit="°C")
        ax_top.set_ylabel("Temperature (°C)", color="crimson")
        ax_top.tick_params(axis="y", labelcolor="crimson")
        ax_top.grid(True, alpha=0.25)

        if humid_col is not None:
            ax_humid = ax_top.twinx()
            ax_humid.plot(
                local.index,
                local[humid_col],
                color="royalblue",
                linewidth=1.3,
                alpha=0.85,
                label="Relative humidity (%)",
            )
            ax_humid.set_ylabel("Relative humidity (%)", color="royalblue")
            ax_humid.tick_params(axis="y", labelcolor="royalblue")
            ax_humid.set_ylim(0, 100)
            self._annotate_extrema(
                ax_humid,
                local[humid_col],
                unit="%",
                value_fmt=".0f",
                colors=("royalblue", "royalblue"),
            )

        # --- Bottom panel: AQI with severity bands + filled area ---
        if has_aqi and ax_aqi is not None:
            top = aqi_max(local)
            for band in AQI_BANDS:
                if band.lower > top:
                    continue
                upper = min(band.upper, top)
                ax_aqi.axhspan(band.lower, upper, color=band.color, alpha=0.18, zorder=0)
                ax_aqi.text(
                    local.index[0],
                    (band.lower + upper) / 2,
                    f" {band.label}",
                    fontsize=8,
                    color="dimgray",
                    va="center",
                    ha="left",
                    zorder=1,
                )
            ax_aqi.fill_between(
                local.index,
                local["us_aqi"],
                0,
                color="black",
                alpha=0.10,
                zorder=2,
            )
            ax_aqi.plot(
                local.index, local["us_aqi"], color="black", linewidth=1.5, label="AQI"
            )
            self._annotate_aqi_max(ax_aqi, local["us_aqi"])
            ax_aqi.set_ylim(0, top)
            ax_aqi.set_ylabel("AQI (0–500)")
            ax_aqi.set_xlabel(f"Time ({query.location.timezone})")
            ax_aqi.grid(True, axis="x", alpha=0.25)
            bottom_axis = ax_aqi
        else:
            ax_top.set_xlabel(f"Time ({query.location.timezone})")
            bottom_axis = ax_top

        bottom_axis.xaxis.set_major_locator(mdates.AutoDateLocator())  # type: ignore[no-untyped-call]
        bottom_axis.xaxis.set_major_formatter(mdates.DateFormatter("%b %d\n%H:%M"))  # type: ignore[no-untyped-call]

        # --- Title + subtitle ---
        title, subtitle = build_title(
            query.location, query.start, query.end, query.granularity, len(df)
        )
        fig.suptitle(title, fontsize=14, fontweight="bold", x=0.02, ha="left")
        fig.text(0.02, 0.935, subtitle, fontsize=9, color="dimgray", ha="left")

        fig.autofmt_xdate()
        fig.tight_layout(rect=(0, 0, 1, 0.92))
        fig.savefig(output, dpi=120)
        plt.close(fig)
        return output

    @staticmethod
    def _annotate_extrema(
        ax: Any,
        series: pd.Series,
        *,
        unit: str,
        value_fmt: str = ".1f",
        colors: tuple[str, str] = ("darkred", "navy"),
    ) -> None:
        clean = series.dropna()
        if clean.empty:
            return
        max_color, min_color = colors
        for label, idx, color, offset in (
            ("max", clean.idxmax(), max_color, (0, 14)),
            ("min", clean.idxmin(), min_color, (0, -18)),
        ):
            value = float(clean.loc[idx])
            ax.annotate(
                f"{label} {value:{value_fmt}}{unit}",
                xy=(idx, value),
                xytext=offset,
                textcoords="offset points",
                fontsize=8,
                color=color,
                ha="center",
                bbox={"boxstyle": "round,pad=0.2", "fc": "white", "ec": color, "alpha": 0.85},
                arrowprops={"arrowstyle": "-", "color": color, "alpha": 0.6},
            )

    @staticmethod
    def _annotate_aqi_max(ax: Any, series: pd.Series) -> None:
        clean = series.dropna()
        if clean.empty:
            return
        for label, idx, dy in (
            ("max", clean.idxmax(), 12),
            ("min", clean.idxmin(), -16),
        ):
            value = float(clean.loc[idx])
            category = aqi_category(value)
            ax.annotate(
                f"{label} {value:.0f} · {category}",
                xy=(idx, value),
                xytext=(0, dy),
                textcoords="offset points",
                fontsize=8,
                color="black",
                ha="center",
                bbox={"boxstyle": "round,pad=0.2", "fc": "white", "ec": "black", "alpha": 0.85},
                arrowprops={"arrowstyle": "-", "color": "black", "alpha": 0.6},
            )
