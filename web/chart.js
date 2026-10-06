// Builds one Plotly figure per chart card (temperature, humidity, AQI) from a
// merged history payload. Each figure has a single y-axis; titles and units
// live in the card's HTML header, so figures carry no title or legend.
// (Started as a port of src/weahist/visualization/plotly_renderer.py; the web
// version has since diverged.)

import { AQI_BANDS, aqiCategory, aqiMax } from "./aqi.js";
import { FONT_FAMILY, paletteFor } from "./theme.js";

export const NARROW_BREAKPOINT = 640;

// Headroom above/below the data so extrema labels stay inside the plot.
const LABEL_PAD = 0.28;

/**
 * @param {object} history result of fetchHistory()
 * @param {"light"|"dark"} theme
 * @returns {{ temperature: Figure|null, humidity: Figure|null, aqi: Figure|null }}
 *   where Figure = { data: any[], layout: any }
 */
export function buildCharts(history, theme) {
  const p = paletteFor(theme);
  const isNarrow = typeof window !== "undefined" && window.innerWidth < NARROW_BREAKPOINT;
  const ctx = { p, isNarrow, times: history.times, granularity: history.granularity };
  const w = history.weather;

  return {
    temperature: seriesChart(ctx, {
      line: w.temperature_2m ?? w.temperature_2m_mean,
      low: w.temperature_2m_min,
      high: w.temperature_2m_max,
      color: p.tempLine,
      unit: " °C",
      digits: 1,
    }),
    humidity: seriesChart(ctx, {
      line: w.relative_humidity_2m ?? w.relative_humidity_2m_mean,
      low: w.relative_humidity_2m_min,
      high: w.relative_humidity_2m_max,
      color: p.humidityLine,
      unit: "%",
      digits: 0,
    }),
    aqi: aqiChart(ctx, history.aqi.us_aqi),
  };
}

/** AQI bands drawn behind the chart for these values (lowest first). */
export function visibleAqiBands(values) {
  const top = aqiMax(values);
  return AQI_BANDS.filter((band) => band.lower <= top);
}

// ---------------------------------------------------------------------

function finite(values) {
  return (values || []).filter((v) => v != null && Number.isFinite(v));
}

function baseLayout({ p, isNarrow, times, granularity }) {
  const tickFont = { size: isNarrow ? 10 : 11, color: p.textMute };
  const layout = {
    template: { layout: { paper_bgcolor: p.paperBg, plot_bgcolor: p.plotBg } },
    paper_bgcolor: p.paperBg,
    plot_bgcolor: p.plotBg,
    font: { color: p.text, family: FONT_FAMILY, size: isNarrow ? 11 : 12 },
    showlegend: false,
    hovermode: "x unified",
    hoverlabel: {
      bgcolor: p.paperBg,
      bordercolor: p.border,
      font: { color: p.text, family: FONT_FAMILY, size: 12 },
    },
    dragmode: isNarrow ? false : "zoom",
    margin: isNarrow ? { t: 8, r: 10, b: 32, l: 40 } : { t: 10, r: 20, b: 36, l: 52 },
    xaxis: {
      type: "date",
      showline: true,
      linecolor: p.border,
      linewidth: 1,
      showgrid: false,
      ticks: "outside",
      tickcolor: p.border,
      ticklen: 4,
      tickfont: tickFont,
      hoverformat: granularity === "hourly" ? "%a %b %-d, %H:%M" : "%a %b %-d, %Y",
      fixedrange: isNarrow,
    },
    yaxis: {
      showline: false,
      gridcolor: p.grid,
      gridwidth: 1,
      zeroline: false,
      tickfont: tickFont,
      nticks: isNarrow ? 4 : 6,
      fixedrange: true,
    },
    shapes: [],
    annotations: [],
  };
  if (granularity === "hourly") addTimeDecorations(layout, times, p);
  return layout;
}

/** A line, or (daily) a low–high band with the mean line on top. */
function seriesChart(ctx, { line, low, high, color, unit, digits }) {
  const { p, times, isNarrow, granularity } = ctx;
  if (!line || finite(line).length === 0) return null;

  const layout = baseLayout(ctx);
  const data = [];
  const fmt = `%{y:.${digits}f}${unit}`;
  const band = granularity === "daily" && finite(low).length > 0 && finite(high).length > 0;

  if (band) {
    data.push({
      type: "scatter",
      mode: "lines",
      name: "High",
      x: times,
      y: high,
      line: { width: 0, color },
      hovertemplate: fmt,
    });
    data.push({
      type: "scatter",
      mode: "lines",
      name: "Low",
      x: times,
      y: low,
      fill: "tonexty",
      fillcolor: hexToRgba(color, 0.14),
      line: { width: 0, color },
      hovertemplate: fmt,
    });
  }
  data.push({
    type: "scatter",
    mode: "lines",
    name: band ? "Mean" : "Value",
    x: times,
    y: line,
    line: { color, width: 2, shape: "spline", smoothing: 0.4 },
    hovertemplate: band ? fmt : `<b>${fmt}</b><extra></extra>`,
  });

  const hiSeries = band ? high : line;
  const loSeries = band ? low : line;
  const lo = Math.min(...finite(loSeries));
  const hi = Math.max(...finite(hiSeries));
  const span = hi - lo || Math.max(Math.abs(hi), 1);
  layout.yaxis.range = [lo - span * LABEL_PAD, hi + span * LABEL_PAD];
  layout.yaxis.ticksuffix = unit.trim() === "%" ? "%" : "°";

  annotateExtreme(layout, times, hiSeries, "max", { p, color, unit, digits, isNarrow });
  annotateExtreme(layout, times, loSeries, "min", { p, color, unit, digits, isNarrow });
  return { data, layout };
}

function aqiChart(ctx, values) {
  const { p, times, isNarrow } = ctx;
  if (!values || finite(values).length === 0) return null;
  // Band names are shown as an HTML legend in the card header (see
  // visibleAqiBands) so they never collide with the line.

  const layout = baseLayout(ctx);
  const top = aqiMax(values);
  const rangeTop = top * (1 + LABEL_PAD / 2);
  layout.yaxis.range = [0, rangeTop];

  const decorations = layout.shapes;
  layout.shapes = [];

  const visible = visibleAqiBands(values);
  visible.forEach((band, i) => {
    const upper = i === visible.length - 1 ? rangeTop : band.upper;
    layout.shapes.push({
      type: "rect",
      xref: "x domain",
      yref: "y",
      x0: 0,
      x1: 1,
      y0: band.lower,
      y1: upper,
      fillcolor: band.color,
      opacity: p.bandOpacity[AQI_BANDS.indexOf(band)],
      line: { width: 0 },
      layer: "below",
    });
  });

  // Day separators/weekends go on top of the bands (shapes draw in order).
  layout.shapes.push(...decorations);

  const data = [
    {
      type: "scatter",
      mode: "lines",
      name: "AQI",
      x: times,
      y: values,
      line: { color: p.aqiLine, width: 2, shape: "spline", smoothing: 0.4 },
      customdata: values.map((v) => (v == null ? "" : aqiCategory(v))),
      hovertemplate: "<b>%{y:.0f}</b> · %{customdata}<extra></extra>",
    },
  ];
  annotateExtreme(layout, times, values, "max", {
    p,
    color: p.aqiLine,
    unit: "",
    digits: 0,
    isNarrow,
  });
  return { data, layout };
}

/** Label the series' max or min with a short ink-colored callout. */
function annotateExtreme(layout, times, values, which, { p, color, unit, digits, isNarrow }) {
  let idx = -1;
  for (let i = 0; i < values.length; i++) {
    const v = values[i];
    if (v == null || !Number.isFinite(v)) continue;
    if (idx === -1 || (which === "max" ? v > values[idx] : v < values[idx])) idx = i;
  }
  if (idx === -1) return;
  layout.annotations.push({
    x: times[idx],
    y: values[idx],
    xref: "x",
    yref: "y",
    text: `${which} ${values[idx].toFixed(digits)}${unit}`,
    showarrow: true,
    arrowhead: 0,
    arrowwidth: 1,
    arrowcolor: color,
    ax: 0,
    ay: which === "max" ? -20 : 20,
    font: { size: isNarrow ? 10 : 11, color: p.text },
    bgcolor: p.annotationBg,
    bordercolor: color,
    borderwidth: 1,
    borderpad: 2,
  });
}

/** Solid hairline day separators and a faint weekend wash (hourly views). */
function addTimeDecorations(layout, times, p) {
  if (times.length === 0) return;
  const days = collectDays(times);
  for (const day of days) {
    const weekday = new Date(`${day}T12:00:00`).getDay();
    if (weekday === 0 || weekday === 6) {
      layout.shapes.push({
        type: "rect",
        xref: "x",
        yref: "y domain",
        x0: `${day}T00:00:00`,
        x1: `${addDays(day, 1)}T00:00:00`,
        y0: 0,
        y1: 1,
        fillcolor: p.weekendFill,
        line: { width: 0 },
        layer: "below",
      });
    }
  }
  for (const day of days.slice(1)) {
    layout.shapes.push({
      type: "line",
      xref: "x",
      yref: "y domain",
      x0: `${day}T00:00:00`,
      x1: `${day}T00:00:00`,
      y0: 0,
      y1: 1,
      line: { color: p.daySeparator, width: 1 },
      layer: "below",
    });
  }
}

/** Distinct "YYYY-MM-DD" days covered by the timestamps, in order. */
function collectDays(times) {
  const out = [];
  let day = times[0].slice(0, 10);
  const last = times[times.length - 1].slice(0, 10);
  while (day <= last) {
    out.push(day);
    day = addDays(day, 1);
  }
  return out;
}

function addDays(ymdStr, n) {
  const d = new Date(`${ymdStr}T12:00:00`);
  d.setDate(d.getDate() + n);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function hexToRgba(hex, alpha) {
  const h = hex.replace("#", "");
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
  return `rgba(${r},${g},${b},${alpha})`;
}
