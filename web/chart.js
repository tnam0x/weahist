// Builds a Plotly figure from a merged history payload.
// Mirrors src/weahist/visualization/plotly_renderer.py.

import { AQI_BANDS, aqiCategory, aqiMax } from "./aqi.js";
import { paletteFor } from "./theme.js";

/**
 * @param {object} history result of fetchHistory()
 * @param {"light"|"dark"} theme
 * @returns {{ data: any[], layout: any }}
 */
export function buildFigure(history, theme) {
  const p = paletteFor(theme);
  const { location, start, end, granularity, times, weather, aqi } = history;

  const tempCol =
    "temperature_2m" in weather
      ? "temperature_2m"
      : "temperature_2m_mean" in weather
      ? "temperature_2m_mean"
      : null;
  const humidCol = "relative_humidity_2m" in weather ? "relative_humidity_2m" : null;
  const hasAqi = aqi.us_aqi && aqi.us_aqi.some((v) => v != null && Number.isFinite(v));

  // Subplot domains (Plotly y-domains are bottom-up; row 1 on top).
  // Match Python make_subplots(row_heights=[0.6, 0.4], vertical_spacing=0.08).
  const layout = {
    template: { layout: { paper_bgcolor: p.paperBg, plot_bgcolor: p.plotBg } },
    paper_bgcolor: p.paperBg,
    plot_bgcolor: p.plotBg,
    font: { color: p.text },
    hovermode: "x unified",
    margin: { t: 130, r: 30, b: 60, l: 70 },
    legend: {
      orientation: "h",
      yanchor: "bottom",
      y: 1.04,
      xanchor: "right",
      x: 1.0,
      bgcolor: p.legendBg,
      bordercolor: p.border,
      borderwidth: 1,
      font: { color: p.text },
    },
    shapes: [],
    annotations: [],
  };

  const tzAxisTitle = `Time (${location.timezone})`;
  const titleText =
    `Weather & Air Quality — ${location.name}` +
    (location.country ? `, ${location.country}` : "");
  const subtitle = `${start} → ${end} · ${granularity} · source: Open-Meteo`;

  layout.title = {
    text: `${titleText}<br><sub>${subtitle}</sub>`,
    x: 0.02,
    xanchor: "left",
    y: 0.97,
    yanchor: "top",
    font: { color: p.text },
  };

  const data = [];

  // Common axis defaults.
  const axisCommon = {
    showline: true,
    linewidth: 1,
    linecolor: p.border,
    mirror: true,
    gridcolor: p.grid,
    color: p.text,
  };

  if (hasAqi) {
    // Two rows. Row 1 [0.448, 1.0], Row 2 [0, 0.368].
    layout.xaxis = { ...axisCommon, anchor: "y", domain: [0, 1] };
    layout.yaxis = {
      ...axisCommon,
      anchor: "x",
      domain: [0.448, 1.0],
      title: { text: "Temperature (°C)", font: { color: p.text } },
    };
    layout.yaxis2 = {
      ...axisCommon,
      anchor: "x",
      overlaying: "y",
      side: "right",
      title: { text: "Humidity (%)", font: { color: p.text } },
      showgrid: false,
    };
    layout.xaxis2 = {
      ...axisCommon,
      anchor: "y3",
      domain: [0, 1],
      matches: "x",
      title: { text: tzAxisTitle, font: { color: p.text } },
    };
    layout.yaxis3 = {
      ...axisCommon,
      anchor: "x2",
      domain: [0, 0.368],
      title: { text: "US AQI (0–500)", font: { color: p.text } },
    };
  } else {
    layout.xaxis = {
      ...axisCommon,
      anchor: "y",
      domain: [0, 1],
      title: { text: tzAxisTitle, font: { color: p.text } },
    };
    layout.yaxis = {
      ...axisCommon,
      anchor: "x",
      domain: [0, 1],
      title: { text: "Temperature (°C)", font: { color: p.text } },
    };
    layout.yaxis2 = {
      ...axisCommon,
      anchor: "x",
      overlaying: "y",
      side: "right",
      title: { text: "Humidity (%)", font: { color: p.text } },
      showgrid: false,
    };
  }

  // Weekend shading + day separators across all rows.
  addTimeDecorations(layout, times, p, hasAqi);

  // Temperature trace.
  if (tempCol) {
    data.push({
      type: "scatter",
      mode: "lines",
      name: "Temperature (°C)",
      x: times,
      y: weather[tempCol],
      xaxis: "x",
      yaxis: "y",
      line: { color: p.tempLine, width: 2 },
      hovertemplate: "<b>%{y:.1f} °C</b><extra>Temperature</extra>",
    });
    annotateExtrema(layout, times, weather[tempCol], p, "°C");
  }

  // Humidity trace.
  if (humidCol) {
    data.push({
      type: "scatter",
      mode: "lines",
      name: "Relative humidity (%)",
      x: times,
      y: weather[humidCol],
      xaxis: "x",
      yaxis: "y2",
      line: { color: p.humidityLine, width: 1.5 },
      hovertemplate: "<b>%{y:.0f}%</b><extra>Humidity</extra>",
    });
  }

  // AQI panel.
  if (hasAqi) {
    const top = aqiMax(aqi.us_aqi);
    layout.yaxis3.range = [0, top];

    AQI_BANDS.forEach((band, i) => {
      if (band.lower > top) return;
      const upper = Math.min(band.upper, top);
      layout.shapes.push({
        type: "rect",
        xref: "x2 domain",
        yref: "y3",
        x0: 0,
        x1: 1,
        y0: band.lower,
        y1: upper,
        fillcolor: band.color,
        opacity: p.bandOpacity[i],
        line: { width: 0 },
        layer: "below",
      });
      layout.annotations.push({
        xref: "x2 domain",
        yref: "y3",
        x: 0.005,
        y: (band.lower + upper) / 2,
        text: band.label,
        showarrow: false,
        xanchor: "left",
        yanchor: "middle",
        font: { size: 10, color: p.textMute },
      });
    });

    const categories = aqi.us_aqi.map((v) =>
      v == null ? "" : aqiCategory(v),
    );
    data.push({
      type: "scatter",
      mode: "lines",
      name: "US AQI",
      x: times,
      y: aqi.us_aqi,
      xaxis: "x2",
      yaxis: "y3",
      line: { color: p.aqiLine, width: 2 },
      customdata: categories,
      hovertemplate: "<b>AQI %{y:.0f}</b> · %{customdata}<extra></extra>",
    });

    annotateAqiExtrema(layout, times, aqi.us_aqi, p);
  }

  return { data, layout };
}

// ---------------------------------------------------------------------

function addTimeDecorations(layout, times, p, hasAqi) {
  if (times.length === 0) return;
  const dayBoundaries = collectDayBoundaries(times);
  const weekendSpans = collectWeekendSpans(dayBoundaries);

  // Build vrect shapes for each row.
  const refs = hasAqi
    ? [{ xref: "x", yref: "y domain" }, { xref: "x2", yref: "y3 domain" }]
    : [{ xref: "x", yref: "y domain" }];

  for (const { xref, yref } of refs) {
    for (const [x0, x1] of weekendSpans) {
      layout.shapes.push({
        type: "rect",
        xref,
        yref,
        x0,
        x1,
        y0: 0,
        y1: 1,
        fillcolor: p.weekendFill,
        line: { width: 0 },
        layer: "below",
      });
    }
    for (const x of dayBoundaries.slice(1, -1)) {
      layout.shapes.push({
        type: "line",
        xref,
        yref,
        x0: x,
        x1: x,
        y0: 0,
        y1: 1,
        line: { color: p.daySeparator, width: 1, dash: "dot" },
        layer: "below",
      });
    }
  }
}

/** Collect midnight timestamps (as ISO strings) for the time range. */
function collectDayBoundaries(times) {
  if (times.length === 0) return [];
  const startDay = times[0].slice(0, 10);
  const endDay = times[times.length - 1].slice(0, 10);
  const out = [];
  const cur = new Date(`${startDay}T00:00:00`);
  const last = new Date(`${endDay}T00:00:00`);
  last.setDate(last.getDate() + 1);
  while (cur <= last) {
    out.push(`${ymd(cur)}T00:00:00`);
    cur.setDate(cur.getDate() + 1);
  }
  return out;
}

function collectWeekendSpans(boundaries) {
  const spans = [];
  for (const b of boundaries) {
    const d = new Date(b);
    if (d.getDay() === 6) {
      // Saturday → 48h span
      const end = new Date(d);
      end.setDate(end.getDate() + 2);
      spans.push([b, `${ymd(end)}T00:00:00`]);
    }
  }
  return spans;
}

function ymd(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function annotateExtrema(layout, times, values, p, unit) {
  const indices = extremaIndices(values);
  if (!indices) return;
  const items = [
    { label: "max", idx: indices.maxIdx, color: p.tempLine, ay: -28 },
    { label: "min", idx: indices.minIdx, color: p.humidityLine, ay: 28 },
  ];
  for (const item of items) {
    const value = values[item.idx];
    layout.annotations.push({
      x: times[item.idx],
      y: value,
      xref: "x",
      yref: "y",
      text: `${item.label} ${value.toFixed(1)}${unit}`,
      showarrow: true,
      arrowhead: 2,
      arrowcolor: item.color,
      ax: 0,
      ay: item.ay,
      font: { size: 10, color: item.color },
      bgcolor: p.annotationBg,
      bordercolor: item.color,
      borderwidth: 1,
    });
  }
}

function annotateAqiExtrema(layout, times, values, p) {
  const indices = extremaIndices(values);
  if (!indices) return;
  for (const [label, idx, ay] of [
    ["max", indices.maxIdx, -24],
    ["min", indices.minIdx, 24],
  ]) {
    const value = values[idx];
    const category = aqiCategory(value);
    layout.annotations.push({
      x: times[idx],
      y: value,
      xref: "x2",
      yref: "y3",
      text: `${label} AQI ${value.toFixed(0)} · ${category}`,
      showarrow: true,
      arrowhead: 2,
      arrowcolor: p.aqiLine,
      ax: 0,
      ay,
      font: { size: 10, color: p.aqiLine },
      bgcolor: p.annotationBg,
      bordercolor: p.aqiLine,
      borderwidth: 1,
    });
  }
}

function extremaIndices(values) {
  let maxIdx = -1;
  let minIdx = -1;
  let max = -Infinity;
  let min = Infinity;
  for (let i = 0; i < values.length; i++) {
    const v = values[i];
    if (v == null || !Number.isFinite(v)) continue;
    if (v > max) { max = v; maxIdx = i; }
    if (v < min) { min = v; minIdx = i; }
  }
  if (maxIdx === -1) return null;
  return { maxIdx, minIdx };
}
