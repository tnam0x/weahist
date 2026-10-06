// Weather History — pure-static frontend.
// Calls Open-Meteo directly from the browser; no backend required.

import { geocode, fetchHistory } from "./api.js";
import { aqiBand } from "./aqi.js";
import { NARROW_BREAKPOINT, buildCharts, visibleAqiBands } from "./chart.js";

const PREFS_KEY = "weahist.prefs.v1";
const DEFAULTS = {
  location: "Hanoi, Vietnam",
  range: "1w",
  theme: "system", // "system" | "light" | "dark"
};
const FETCH_TIMEOUT_MS = 30_000;

// ---- Preferences ------------------------------------------------------
function loadPrefs() {
  try {
    const raw = localStorage.getItem(PREFS_KEY);
    if (!raw) return { ...DEFAULTS };
    return { ...DEFAULTS, ...JSON.parse(raw) };
  } catch {
    return { ...DEFAULTS };
  }
}
function savePrefs(prefs) {
  try {
    localStorage.setItem(PREFS_KEY, JSON.stringify(prefs));
  } catch { /* storage unavailable */ }
}

const prefs = loadPrefs();

// URL params override saved prefs (shareable links).
const urlParams = new URLSearchParams(window.location.search);
if (urlParams.get("location")) prefs.location = urlParams.get("location");
if (urlParams.get("range")) prefs.range = urlParams.get("range");
if (urlParams.get("theme")) prefs.theme = urlParams.get("theme");

// ---- Theme ------------------------------------------------------------
const themeSelect = document.getElementById("theme-select");
const mql = window.matchMedia("(prefers-color-scheme: dark)");

function effectiveTheme() {
  if (prefs.theme === "system") return mql.matches ? "dark" : "light";
  return prefs.theme;
}
function applyTheme() {
  document.documentElement.setAttribute("data-theme", effectiveTheme());
}

themeSelect.value = prefs.theme;
themeSelect.addEventListener("change", () => {
  prefs.theme = themeSelect.value;
  savePrefs(prefs);
  applyTheme();
  rerenderChartIfData();
});
mql.addEventListener("change", () => {
  if (prefs.theme === "system") {
    applyTheme();
    rerenderChartIfData();
  }
});
applyTheme();

// ---- Chart cards --------------------------------------------------------
const CHART_KEYS = ["temperature", "humidity", "aqi"];
const cards = Object.fromEntries(
  CHART_KEYS.map((key) => {
    const card = document.querySelector(`.chart-card[data-chart="${key}"]`);
    return [
      key,
      {
        card,
        chart: card.querySelector(".chart"),
        wrap: card.querySelector(".chart-wrap"),
        table: card.querySelector(".table-wrap"),
        empty: card.querySelector(".card-empty"),
        sub: card.querySelector(".card-sub"),
        toggle: card.querySelector('[data-action="table"]'),
        legend: card.querySelector(".band-legend"),
      },
    ];
  }),
);

// ---- Controls ---------------------------------------------------------
const locInput = document.getElementById("location-input");
const rangeSelect = document.getElementById("range-select");
const suggestionsEl = document.getElementById("location-suggestions");
const statusEl = document.getElementById("status");
const kpisEl = document.getElementById("kpis");
const placeTitleEl = document.getElementById("place-title");
const rangeSubtitleEl = document.getElementById("range-subtitle");
const loadingEl = document.getElementById("loading");
const errorBanner = document.getElementById("error-banner");
const errorBannerText = document.getElementById("error-banner-text");

locInput.value = prefs.location;
rangeSelect.value = prefs.range;

rangeSelect.addEventListener("change", () => {
  prefs.range = rangeSelect.value;
  savePrefs(prefs);
  refreshChart();
});

// ---- Location autocomplete -------------------------------------------
let acTimer = null;
let acResults = [];
let acActive = -1;
let acAbort = null;

function debounce(fn, ms) {
  return (...args) => {
    clearTimeout(acTimer);
    acTimer = setTimeout(() => fn(...args), ms);
  };
}

async function searchLocations(q) {
  if (!q || q.trim().length < 2) {
    hideSuggestions();
    return;
  }
  if (acAbort) acAbort.abort();
  const ctrl = new AbortController();
  acAbort = ctrl;
  try {
    acResults = await geocode(q, { count: 6, signal: ctrl.signal });
    renderSuggestions();
  } catch (err) {
    if (err.name !== "AbortError") {
      // Silent — typeahead is non-critical.
      console.warn("geocode failed:", err);
    }
  }
}
function renderSuggestions() {
  if (acResults.length === 0) {
    hideSuggestions();
    return;
  }
  suggestionsEl.innerHTML = acResults
    .map((r, i) =>
      `<li data-idx="${i}" class="${i === acActive ? "active" : ""}">${escapeHtml(r.label)}</li>`,
    )
    .join("");
  suggestionsEl.hidden = false;
}
function hideSuggestions() {
  suggestionsEl.hidden = true;
  suggestionsEl.innerHTML = "";
  acActive = -1;
}
function pickSuggestion(idx) {
  const r = acResults[idx];
  if (!r) return;
  selectedLocation = r;
  locInput.value = r.label;
  prefs.location = r.label;
  prefs.locationResolved = r;
  savePrefs(prefs);
  hideSuggestions();
  refreshChart();
}

locInput.addEventListener(
  "input",
  debounce((e) => searchLocations(e.target.value), 250),
);

locInput.addEventListener("keydown", (e) => {
  if (suggestionsEl.hidden) {
    if (e.key === "Enter") {
      prefs.location = locInput.value.trim();
      delete prefs.locationResolved;
      savePrefs(prefs);
      selectedLocation = null;
      refreshChart();
    }
    return;
  }
  if (e.key === "ArrowDown") {
    e.preventDefault();
    acActive = (acActive + 1) % acResults.length;
    renderSuggestions();
  } else if (e.key === "ArrowUp") {
    e.preventDefault();
    acActive = (acActive - 1 + acResults.length) % acResults.length;
    renderSuggestions();
  } else if (e.key === "Enter") {
    e.preventDefault();
    if (acActive >= 0) pickSuggestion(acActive);
    else {
      prefs.location = locInput.value.trim();
      delete prefs.locationResolved;
      savePrefs(prefs);
      hideSuggestions();
      selectedLocation = null;
      refreshChart();
    }
  } else if (e.key === "Escape") {
    hideSuggestions();
  }
});

suggestionsEl.addEventListener("mousedown", (e) => {
  const li = e.target.closest("li");
  if (!li) return;
  e.preventDefault();
  pickSuggestion(Number(li.dataset.idx));
});

document.addEventListener("click", (e) => {
  if (!locInput.contains(e.target) && !suggestionsEl.contains(e.target)) {
    hideSuggestions();
  }
});

// ---- Reset prefs ------------------------------------------------------
document.getElementById("reset-prefs").addEventListener("click", (e) => {
  e.preventDefault();
  localStorage.removeItem(PREFS_KEY);
  Object.assign(prefs, DEFAULTS);
  locInput.value = prefs.location;
  rangeSelect.value = prefs.range;
  themeSelect.value = prefs.theme;
  selectedLocation = null;
  applyTheme();
  refreshChart();
});

// ---- Error banner -----------------------------------------------------
document
  .getElementById("error-banner-close")
  .addEventListener("click", () => hideErrorBanner());

function showErrorBanner(message) {
  errorBannerText.textContent = message;
  errorBanner.hidden = false;
}
function hideErrorBanner() {
  errorBanner.hidden = true;
  errorBannerText.textContent = "";
}

// ---- Loading state ----------------------------------------------------
let loadingDepth = 0;
function setLoading(on) {
  loadingDepth = Math.max(0, loadingDepth + (on ? 1 : -1));
  const active = loadingDepth > 0;
  loadingEl.hidden = !active;
  document.body.classList.toggle("is-loading", active);
}

// ---- Chart fetch + render --------------------------------------------
let inFlight = null;
let lastHistory = null; // cached for cheap theme re-renders
let selectedLocation =
  prefs.locationResolved && prefs.locationResolved.label === prefs.location
    ? prefs.locationResolved
    : null;

function rangeLabel(key) {
  const opt = rangeSelect.querySelector(`option[value="${key}"]`);
  return opt ? opt.textContent : key;
}
function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

async function rerenderChartIfData() {
  if (lastHistory) await renderCharts(lastHistory);
}

const EMPTY_MESSAGES = {
  temperature: "No temperature data for this period.",
  humidity: "No humidity data for this period.",
  aqi: "No air-quality data for this period — it typically covers only the last 2–3 years.",
};

function cardSubtitle(key, history) {
  const daily = history.granularity === "daily";
  if (key === "temperature") return daily ? "°C · daily low–high range and mean" : "°C · hourly";
  if (key === "humidity") return daily ? "% · daily low–high range and mean" : "% · hourly";
  return daily ? "US AQI · daily mean" : "US AQI · hourly";
}

async function renderCharts(history) {
  const figs = buildCharts(history, effectiveTheme());
  const config = plotlyConfig();
  await Promise.all(
    CHART_KEYS.map(async (key) => {
      const c = cards[key];
      const fig = figs[key];
      c.sub.textContent = cardSubtitle(key, history);
      if (c.legend) renderBandLegend(c.legend, fig ? history.aqi.us_aqi : null);
      c.empty.hidden = Boolean(fig);
      c.toggle.hidden = !fig;
      if (!fig) {
        c.empty.textContent = EMPTY_MESSAGES[key];
        c.wrap.hidden = true;
        c.table.hidden = true;
        Plotly.purge(c.chart);
        return;
      }
      const showTable = c.toggle.getAttribute("aria-pressed") === "true";
      c.wrap.hidden = showTable;
      c.table.hidden = !showTable;
      if (showTable) renderTable(key, history);
      await Plotly.react(c.chart, fig.data, fig.layout, config);
      bindSync(c.chart);
    }),
  );
}

function renderBandLegend(listEl, values) {
  if (!values) {
    listEl.hidden = true;
    return;
  }
  listEl.replaceChildren(
    ...visibleAqiBands(values).map((band) => {
      const item = el("li");
      const swatch = el("span", "band-swatch");
      swatch.style.background = band.color;
      item.append(swatch, document.createTextNode(band.label));
      return item;
    }),
  );
  listEl.hidden = false;
}

// ---- Table view (the accessible twin of each chart) ---------------------
function tableColumns(key, history) {
  const w = history.weather;
  const daily = history.granularity === "daily";
  if (key === "temperature") {
    return daily
      ? [
          ["Low (°C)", w.temperature_2m_min, 1],
          ["Mean (°C)", w.temperature_2m_mean, 1],
          ["High (°C)", w.temperature_2m_max, 1],
        ]
      : [["Temperature (°C)", w.temperature_2m, 1]];
  }
  if (key === "humidity") {
    return daily
      ? [
          ["Low (%)", w.relative_humidity_2m_min, 0],
          ["Mean (%)", w.relative_humidity_2m_mean, 0],
          ["High (%)", w.relative_humidity_2m_max, 0],
        ]
      : [["Humidity (%)", w.relative_humidity_2m, 0]];
  }
  return [
    ["US AQI", history.aqi.us_aqi, 0],
    ["PM2.5 (µg/m³)", history.aqi.pm2_5, 1],
    ["PM10 (µg/m³)", history.aqi.pm10, 1],
  ];
}

function renderTable(key, history) {
  const columns = tableColumns(key, history);
  const table = el("table", "data-table");
  table.setAttribute("aria-label", `${cards[key].card.querySelector(".card-title").textContent} data`);
  const headRow = el("tr");
  headRow.append(el("th", null, history.granularity === "daily" ? "Date" : "Time"));
  for (const [label] of columns) headRow.append(el("th", null, label));
  const head = el("thead");
  head.append(headRow);
  table.append(head);
  const body = el("tbody");
  history.times.forEach((t, i) => {
    const row = el("tr");
    row.append(el("td", null, t.replace("T", " ")));
    for (const [, values, digits] of columns) {
      const v = values?.[i];
      row.append(el("td", null, v == null || !Number.isFinite(v) ? "—" : v.toFixed(digits)));
    }
    body.append(row);
  });
  table.append(body);
  cards[key].table.replaceChildren(table);
}

for (const key of CHART_KEYS) {
  const c = cards[key];
  c.toggle.addEventListener("click", () => {
    const show = c.toggle.getAttribute("aria-pressed") !== "true";
    c.toggle.setAttribute("aria-pressed", String(show));
    c.toggle.textContent = show ? "Chart" : "Table";
    if (show && lastHistory) renderTable(key, lastHistory);
    c.table.hidden = !show;
    c.wrap.hidden = show;
    if (!show && c.chart._fullLayout) Plotly.Plots.resize(c.chart);
  });
}

// ---- Synced crosshair & zoom across cards --------------------------------
let syncing = false;
function otherCharts(div) {
  return CHART_KEYS.map((k) => cards[k])
    .filter((c) => c.chart !== div && c.chart._fullLayout && !c.wrap.hidden)
    .map((c) => c.chart);
}
function bindSync(div) {
  if (div.dataset.synced) return;
  div.dataset.synced = "1";
  div.on("plotly_hover", (ev) => {
    if (syncing || !ev.xvals) return;
    syncing = true;
    try {
      for (const other of otherCharts(div)) Plotly.Fx.hover(other, { xval: ev.xvals[0] });
    } finally {
      syncing = false;
    }
  });
  div.on("plotly_unhover", () => {
    if (syncing) return;
    syncing = true;
    try {
      for (const other of otherCharts(div)) Plotly.Fx.unhover(other);
    } finally {
      syncing = false;
    }
  });
  div.on("plotly_relayout", (ev) => {
    if (syncing) return;
    const update = Object.fromEntries(
      Object.entries(ev).filter(([k]) => k.startsWith("xaxis.range") || k === "xaxis.autorange"),
    );
    if (Object.keys(update).length === 0) return;
    syncing = true;
    Promise.all(otherCharts(div).map((other) => Plotly.relayout(other, update))).finally(() => {
      syncing = false;
    });
  });
}

function plotlyConfig() {
  const hasHover =
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(hover: hover)").matches;
  return {
    responsive: true,
    displaylogo: false,
    displayModeBar: hasHover ? "hover" : false,
    modeBarButtonsToRemove: ["lasso2d", "select2d"],
  };
}

async function refreshChart() {
  const locText = (prefs.location || "").trim();
  if (!locText) {
    statusEl.textContent = "Enter a location to begin.";
    return;
  }

  // Only the first load gets a status line; refetches keep the previous
  // render (dimmed) so nothing jumps.
  if (!lastHistory) statusEl.textContent = `Loading ${locText} (${rangeLabel(prefs.range)})…`;
  hideErrorBanner();

  if (inFlight) inFlight.abort();
  const ctrl = new AbortController();
  inFlight = ctrl;
  const timer = setTimeout(
    () => ctrl.abort(new DOMException("timeout", "TimeoutError")),
    FETCH_TIMEOUT_MS,
  );
  setLoading(true);

  try {
    let location = selectedLocation;
    if (!location || location.label !== locText) {
      let matches = await geocode(locText, { count: 1, signal: ctrl.signal });
      // Saved labels can include admin1 (e.g. "Hanoi, Hanoi, Vietnam")
      // which the geocoder doesn't match — retry with the leading segment.
      if (matches.length === 0 && locText.includes(",")) {
        const head = locText.split(",")[0].trim();
        if (head) {
          matches = await geocode(head, { count: 1, signal: ctrl.signal });
        }
      }
      if (matches.length === 0) throw new Error(`No matches for "${locText}"`);
      location = matches[0];
      selectedLocation = location;
      prefs.locationResolved = location;
      savePrefs(prefs);
    }
    const history = await fetchHistory(location, prefs.range, {
      signal: ctrl.signal,
    });
    lastHistory = history;
    statusEl.textContent = "";
    renderHeading(history);
    renderKpis(history);
    await renderCharts(history);
  } catch (err) {
    if (err.name === "AbortError" && ctrl.signal.reason?.name !== "TimeoutError") {
      return; // superseded by a newer request
    }
    const msg =
      err.name === "AbortError" || err.name === "TimeoutError"
        ? `Request timed out after ${FETCH_TIMEOUT_MS / 1000}s. Try a smaller range or check your network.`
        : `Failed to fetch data: ${err.message}`;
    statusEl.textContent = "";
    showErrorBanner(msg);
  } finally {
    clearTimeout(timer);
    if (inFlight === ctrl) inFlight = null;
    setLoading(false);
  }
}

// ---- Card heading & KPI tiles -----------------------------------------
const DATE_FMT = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  year: "numeric",
});

/** "2026-03-09" -> "Mar 9, 2026" (parsed at noon so no timezone can shift the day). */
function formatDate(ymd) {
  return DATE_FMT.format(new Date(`${ymd}T12:00:00`));
}

function renderHeading(history) {
  const { location, start, end, granularity } = history;
  placeTitleEl.textContent = [location.name, location.country].filter(Boolean).join(", ");
  const granularityLabel = granularity.charAt(0).toUpperCase() + granularity.slice(1);
  const range = start === end ? formatDate(start) : `${formatDate(start)} – ${formatDate(end)}`;
  rangeSubtitleEl.textContent = `${range} · ${granularityLabel} · ${location.timezone}`;
}

function finite(values) {
  return (values || []).filter((v) => v != null && Number.isFinite(v));
}
function mean(values) {
  return values.reduce((a, b) => a + b, 0) / values.length;
}

/** { avg, low, high } over an hourly column, or daily mean/min/max columns. */
function stats(weather, hourlyCol, dailyPrefix) {
  if (hourlyCol in weather) {
    const v = finite(weather[hourlyCol]);
    return v.length ? { avg: mean(v), low: Math.min(...v), high: Math.max(...v) } : null;
  }
  const avg = finite(weather[`${dailyPrefix}_mean`]);
  const lows = finite(weather[`${dailyPrefix}_min`]);
  const highs = finite(weather[`${dailyPrefix}_max`]);
  if (!avg.length) return null;
  return {
    avg: mean(avg),
    low: Math.min(...(lows.length ? lows : avg)),
    high: Math.max(...(highs.length ? highs : avg)),
  };
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function kpiTile(key, label, value, sub) {
  const tile = el("div", "kpi");
  tile.dataset.kpi = key;
  const valueEl = el("div", "kpi-value");
  if (value instanceof Node) valueEl.append(value);
  else valueEl.textContent = value;
  tile.append(el("div", "kpi-label", label), valueEl, el("div", "kpi-sub", sub));
  return tile;
}

function renderKpis(history) {
  const tiles = [];
  const temp = stats(history.weather, "temperature_2m", "temperature_2m");
  tiles.push(
    temp
      ? kpiTile(
          "temperature",
          "Avg temperature",
          `${temp.avg.toFixed(1)} °C`,
          `Low ${temp.low.toFixed(1)} · High ${temp.high.toFixed(1)} °C`,
        )
      : kpiTile("temperature", "Avg temperature", "—", "No data"),
  );

  const humid = stats(history.weather, "relative_humidity_2m", "relative_humidity_2m");
  tiles.push(
    humid
      ? kpiTile(
          "humidity",
          "Avg humidity",
          `${humid.avg.toFixed(0)}%`,
          `Low ${humid.low.toFixed(0)} · High ${humid.high.toFixed(0)}%`,
        )
      : kpiTile("humidity", "Avg humidity", "—", "No data"),
  );

  const aqis = finite(history.aqi.us_aqi);
  if (aqis.length) {
    const peak = Math.max(...aqis);
    const band = aqiBand(peak);
    const value = document.createDocumentFragment();
    const badge = el("span", "aqi-badge");
    const dot = el("span", "aqi-dot");
    dot.style.background = band.color;
    badge.append(dot, document.createTextNode(band.label));
    value.append(document.createTextNode(peak.toFixed(0)), badge);
    tiles.push(kpiTile("aqi", "Peak AQI (US)", value, band.advice));
  } else {
    tiles.push(kpiTile("aqi", "Peak AQI (US)", "—", "No air-quality data for this period"));
  }

  const n = history.times.length;
  tiles.push(
    kpiTile(
      "coverage",
      "AQI coverage",
      `${(history.aqiCoverage * 100).toFixed(0)}%`,
      `${n} ${history.granularity} ${n === 1 ? "reading" : "readings"}`,
    ),
  );

  kpisEl.replaceChildren(...tiles);
  kpisEl.hidden = false;
}

// Initial render.
refreshChart();

// Re-render chart on viewport size / orientation changes so the
// mobile vs. desktop layout switches correctly.
let resizeTimer = null;
let wasNarrow = window.innerWidth < NARROW_BREAKPOINT;
function onViewportChange() {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    const isNarrow = window.innerWidth < NARROW_BREAKPOINT;
    // Only re-render when crossing the breakpoint to avoid thrashing.
    if (isNarrow !== wasNarrow) {
      wasNarrow = isNarrow;
      rerenderChartIfData();
    }
  }, 150);
}
window.addEventListener("resize", onViewportChange);
window.addEventListener("orientationchange", onViewportChange);
