// Weather History — pure-static frontend.
// Calls Open-Meteo directly from the browser; no backend required.

import {
  RANGE_LABELS,
  fetchHistory,
  geocode,
  todayYmd,
  validateCustomRange,
} from "./api.js";
import { aqiBand } from "./aqi.js";
import { NARROW_BREAKPOINT, buildCharts, visibleAqiBands } from "./chart.js";

const PREFS_KEY = "weahist.prefs.v1";
const DEFAULTS = {
  location: "Hanoi, Vietnam",
  range: "1w", // a RANGE_LABELS key, or "custom" (uses start/end)
  theme: "system", // "system" | "light" | "dark"
  units: "c", // "c" | "f"
};
const MAX_RECENT = 5;
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
if (urlParams.get("start") && urlParams.get("end")) {
  prefs.range = "custom";
  prefs.start = urlParams.get("start");
  prefs.end = urlParams.get("end");
}
if (urlParams.get("theme")) prefs.theme = urlParams.get("theme");
if (["c", "f"].includes(urlParams.get("units"))) prefs.units = urlParams.get("units");
// Fall back to the default preset if the saved/shared range is unusable.
if (
  prefs.range === "custom"
    ? validateCustomRange(prefs.start, prefs.end) !== null
    : !(prefs.range in RANGE_LABELS)
) {
  prefs.range = DEFAULTS.range;
}

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
        png: card.querySelector('[data-action="png"]'),
        legend: card.querySelector(".band-legend"),
      },
    ];
  }),
);

// ---- Controls ---------------------------------------------------------
const locInput = document.getElementById("location-input");
const rangeChips = [...document.querySelectorAll("#range-chips .chip")];
const customToggle = document.getElementById("custom-toggle");
const customForm = document.getElementById("custom-range");
const customStart = document.getElementById("custom-start");
const customEnd = document.getElementById("custom-end");
const customError = document.getElementById("custom-error");
const unitChips = [...document.querySelectorAll("#units .chip")];
const locateBtn = document.getElementById("locate");
const suggestionsEl = document.getElementById("location-suggestions");
const statusEl = document.getElementById("status");
const kpisEl = document.getElementById("kpis");
const placeTitleEl = document.getElementById("place-title");
const rangeSubtitleEl = document.getElementById("range-subtitle");
const loadingEl = document.getElementById("loading");
const errorBanner = document.getElementById("error-banner");
const errorBannerText = document.getElementById("error-banner-text");

locInput.value = prefs.location;

// ---- Time range: preset chips + custom dates ----------------------------
function syncRangeUI() {
  for (const chip of rangeChips) {
    const on = chip.dataset.range === prefs.range;
    chip.setAttribute("aria-checked", String(on));
    // Roving tabindex: only the checked chip (or the first) is tabbable.
    chip.tabIndex = on || (prefs.range === "custom" && chip === rangeChips[0]) ? 0 : -1;
  }
  customToggle.setAttribute("aria-pressed", String(prefs.range === "custom"));
}

function selectRange(key) {
  prefs.range = key;
  delete prefs.start;
  delete prefs.end;
  savePrefs(prefs);
  syncRangeUI();
  closeCustomForm();
  refreshChart();
}

rangeChips.forEach((chip, i) => {
  chip.addEventListener("click", () => selectRange(chip.dataset.range));
  chip.addEventListener("keydown", (e) => {
    const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
    if (!step) return;
    e.preventDefault();
    const next = rangeChips[(i + step + rangeChips.length) % rangeChips.length];
    next.focus();
    selectRange(next.dataset.range);
  });
});

function openCustomForm() {
  const today = todayYmd();
  customStart.max = today;
  customEnd.max = today;
  customStart.min = "1940-01-01";
  customEnd.min = "1940-01-01";
  const current = lastHistory ?? null;
  customStart.value = prefs.start ?? current?.start ?? "";
  customEnd.value = prefs.end ?? current?.end ?? today;
  customError.textContent = "";
  customForm.hidden = false;
  customToggle.setAttribute("aria-expanded", "true");
  customStart.focus();
}
function closeCustomForm() {
  customForm.hidden = true;
  customToggle.setAttribute("aria-expanded", "false");
}

customToggle.addEventListener("click", () => {
  if (customForm.hidden) openCustomForm();
  else closeCustomForm();
});
customForm.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    closeCustomForm();
    customToggle.focus();
  }
});
customForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const error = validateCustomRange(customStart.value, customEnd.value);
  customError.textContent = error ?? "";
  if (error) return;
  prefs.range = "custom";
  prefs.start = customStart.value;
  prefs.end = customEnd.value;
  savePrefs(prefs);
  syncRangeUI();
  closeCustomForm();
  refreshChart();
});

syncRangeUI();

/** What to pass to fetchHistory: a preset key or { start, end }. */
function currentRange() {
  return prefs.range === "custom" ? { start: prefs.start, end: prefs.end } : prefs.range;
}
function currentRangeLabel() {
  return prefs.range === "custom"
    ? `${formatDate(prefs.start)} – ${formatDate(prefs.end)}`
    : RANGE_LABELS[prefs.range];
}

// ---- Units --------------------------------------------------------------
function syncUnitsUI() {
  for (const chip of unitChips) {
    const on = chip.dataset.units === prefs.units;
    chip.setAttribute("aria-checked", String(on));
    chip.tabIndex = on ? 0 : -1;
  }
}
unitChips.forEach((chip) => {
  chip.addEventListener("click", () => setUnits(chip.dataset.units));
  chip.addEventListener("keydown", (e) => {
    if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(e.key)) return;
    e.preventDefault();
    const other = unitChips.find((c) => c !== chip);
    other.focus();
    setUnits(other.dataset.units);
  });
});
function setUnits(units) {
  if (prefs.units === units) return;
  prefs.units = units;
  savePrefs(prefs);
  syncUnitsUI();
  if (lastHistory) {
    renderKpis(lastHistory);
    renderCharts(lastHistory);
  }
}
syncUnitsUI();

const TEMP_COLUMNS = ["temperature_2m", "temperature_2m_mean", "temperature_2m_min", "temperature_2m_max"];

/** The history with temperatures in the user's unit, plus `tempUnit`. */
function withUnits(history) {
  if (prefs.units !== "f") return { ...history, tempUnit: "°C" };
  const weather = { ...history.weather };
  for (const col of TEMP_COLUMNS) {
    if (weather[col]) weather[col] = weather[col].map((v) => (v == null ? v : (v * 9) / 5 + 32));
  }
  return { ...history, weather, tempUnit: "°F" };
}

// ---- My location ----------------------------------------------------------
locateBtn.addEventListener("click", () => {
  if (!navigator.geolocation) {
    showErrorBanner("Location isn't available in this browser.");
    return;
  }
  locateBtn.setAttribute("aria-busy", "true");
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      locateBtn.removeAttribute("aria-busy");
      const { latitude, longitude } = pos.coords;
      const loc = {
        name: "My location",
        country: "",
        admin1: "",
        latitude,
        longitude,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
        label: `My location (${latitude.toFixed(2)}, ${longitude.toFixed(2)})`,
      };
      useLocation(loc);
    },
    (err) => {
      locateBtn.removeAttribute("aria-busy");
      const reason =
        err.code === err.PERMISSION_DENIED
          ? "permission was denied"
          : err.code === err.TIMEOUT
          ? "it took too long"
          : "your position is unavailable";
      showErrorBanner(`Couldn't use your location: ${reason}.`);
    },
    { timeout: 10_000, maximumAge: 10 * 60_000 },
  );
});

/** Switch to an already-resolved location and reload. */
function useLocation(loc) {
  selectedLocation = loc;
  locInput.value = loc.label;
  prefs.location = loc.label;
  prefs.locationResolved = loc;
  savePrefs(prefs);
  hideSuggestions();
  refreshChart();
}

function rememberLocation(loc) {
  const recent = (prefs.recent || []).filter((r) => r.label !== loc.label);
  prefs.recent = [loc, ...recent].slice(0, MAX_RECENT);
  savePrefs(prefs);
}

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
    showRecent();
    return;
  }
  if (acAbort) acAbort.abort();
  const ctrl = new AbortController();
  acAbort = ctrl;
  try {
    acResults = await geocode(q, { count: 6, signal: ctrl.signal });
    acHeading = null;
    renderSuggestions();
  } catch (err) {
    if (err.name !== "AbortError") {
      // Silent — typeahead is non-critical.
      console.warn("geocode failed:", err);
    }
  }
}
let acHeading = null; // e.g. "Recent" above the list
function renderSuggestions() {
  if (acResults.length === 0) {
    hideSuggestions();
    return;
  }
  const head = acHeading
    ? `<li class="suggestions-head" role="presentation">${escapeHtml(acHeading)}</li>`
    : "";
  suggestionsEl.innerHTML =
    head +
    acResults
      .map(
        (r, i) =>
          `<li data-idx="${i}" role="option" aria-selected="${i === acActive}" class="${i === acActive ? "active" : ""}">${escapeHtml(r.label)}</li>`,
      )
      .join("");
  suggestionsEl.hidden = false;
  locInput.setAttribute("aria-expanded", "true");
}
function hideSuggestions() {
  suggestionsEl.hidden = true;
  suggestionsEl.innerHTML = "";
  acActive = -1;
  locInput.setAttribute("aria-expanded", "false");
}
function showRecent() {
  if (acAbort) acAbort.abort();
  acResults = prefs.recent || [];
  acHeading = "Recent";
  acActive = -1;
  renderSuggestions();
}
function pickSuggestion(idx) {
  const r = acResults[idx];
  if (r) useLocation(r);
}

locInput.addEventListener("focus", () => {
  if (suggestionsEl.hidden) showRecent();
});

// Drop the "Recent" list as soon as a real query is typed, so a stale
// entry can't be clicked while the search is still debouncing.
locInput.addEventListener("input", () => {
  if (acHeading && locInput.value.trim().length >= 2) hideSuggestions();
});

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
  themeSelect.value = prefs.theme;
  syncRangeUI();
  syncUnitsUI();
  closeCustomForm();
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
  const u = history.tempUnit;
  if (key === "temperature") return daily ? `${u} · daily low–high range and mean` : `${u} · hourly`;
  if (key === "humidity") return daily ? "% · daily low–high range and mean" : "% · hourly";
  return daily ? "US AQI · daily mean" : "US AQI · hourly";
}

async function renderCharts(rawHistory) {
  const history = withUnits(rawHistory);
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
      c.png.hidden = !fig;
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
  const u = history.tempUnit;
  const daily = history.granularity === "daily";
  if (key === "temperature") {
    return daily
      ? [
          [`Low (${u})`, w.temperature_2m_min, 1],
          [`Mean (${u})`, w.temperature_2m_mean, 1],
          [`High (${u})`, w.temperature_2m_max, 1],
        ]
      : [[`Temperature (${u})`, w.temperature_2m, 1]];
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

function renderTable(key, rawHistory) {
  const history = withUnits(rawHistory);
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

// ---- Share & export -----------------------------------------------------
const shareBtn = document.getElementById("share");
const csvBtn = document.getElementById("download-csv");
const toastEl = document.getElementById("toast");

let toastTimer = null;
function showToast(message) {
  toastEl.textContent = message;
  toastEl.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toastEl.hidden = true;
  }, 2500);
}

/** A link that reopens exactly the current view. */
function shareUrl() {
  const params = new URLSearchParams();
  params.set("location", prefs.location);
  if (prefs.range === "custom") {
    params.set("start", prefs.start);
    params.set("end", prefs.end);
  } else {
    params.set("range", prefs.range);
  }
  if (prefs.units !== DEFAULTS.units) params.set("units", prefs.units);
  if (prefs.theme !== DEFAULTS.theme) params.set("theme", prefs.theme);
  return `${window.location.origin}${window.location.pathname}?${params}`;
}

shareBtn.addEventListener("click", async () => {
  const url = shareUrl();
  const coarse = window.matchMedia("(pointer: coarse)").matches;
  if (coarse && navigator.share) {
    try {
      await navigator.share({ title: document.title, url });
    } catch (err) {
      if (err.name !== "AbortError") showToast("Couldn't open the share sheet.");
    }
    return;
  }
  try {
    await navigator.clipboard.writeText(url);
    showToast("Link copied");
  } catch {
    showToast("Couldn't copy — use the link in the address bar.");
    history.replaceState(null, "", url);
  }
});

function fileSlug(history) {
  const place = (history.location.name || "location")
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
  return `weahist-${place || "location"}-${history.start}_${history.end}`;
}

function csvCell(v) {
  if (v == null || (typeof v === "number" && !Number.isFinite(v))) return "";
  const text = String(v);
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function buildCsv(rawHistory) {
  const history = withUnits(rawHistory);
  const u = history.tempUnit === "°F" ? "F" : "C";
  const w = history.weather;
  const columns =
    history.granularity === "daily"
      ? [
          [`temperature_min_${u}`, w.temperature_2m_min],
          [`temperature_mean_${u}`, w.temperature_2m_mean],
          [`temperature_max_${u}`, w.temperature_2m_max],
          ["humidity_min_pct", w.relative_humidity_2m_min],
          ["humidity_mean_pct", w.relative_humidity_2m_mean],
          ["humidity_max_pct", w.relative_humidity_2m_max],
        ]
      : [
          [`temperature_${u}`, w.temperature_2m],
          ["humidity_pct", w.relative_humidity_2m],
        ];
  columns.push(
    ["us_aqi", history.aqi.us_aqi],
    ["pm2_5_ugm3", history.aqi.pm2_5],
    ["pm10_ugm3", history.aqi.pm10],
  );
  const round = (v) => (typeof v === "number" ? Math.round(v * 100) / 100 : v);
  const lines = [["time", ...columns.map(([name]) => name)].join(",")];
  history.times.forEach((t, i) => {
    lines.push([t, ...columns.map(([, values]) => round(values?.[i]))].map(csvCell).join(","));
  });
  return `${lines.join("\n")}\n`;
}

csvBtn.addEventListener("click", () => {
  if (!lastHistory) return;
  const blob = new Blob([buildCsv(lastHistory)], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = el("a");
  a.href = url;
  a.download = `${fileSlug(lastHistory)}.csv`;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});

for (const key of CHART_KEYS) {
  cards[key].png.addEventListener("click", () => {
    const c = cards[key];
    if (!lastHistory || !c.chart._fullLayout) return;
    Plotly.downloadImage(c.chart, {
      format: "png",
      filename: `${fileSlug(lastHistory)}-${key}`,
      width: 1200,
      height: 400,
      scale: 2,
    });
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
  if (!lastHistory) statusEl.textContent = `Loading ${locText} (${currentRangeLabel()})…`;
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
    const history = await fetchHistory(location, currentRange(), {
      signal: ctrl.signal,
    });
    lastHistory = history;
    rememberLocation(location);
    statusEl.textContent = "";
    renderHeading(history);
    renderKpis(history);
    csvBtn.hidden = false;
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

function renderKpis(rawHistory) {
  const history = withUnits(rawHistory);
  const u = history.tempUnit;
  const tiles = [];
  const temp = stats(history.weather, "temperature_2m", "temperature_2m");
  tiles.push(
    temp
      ? kpiTile(
          "temperature",
          "Avg temperature",
          `${temp.avg.toFixed(1)} ${u}`,
          `Low ${temp.low.toFixed(1)} · High ${temp.high.toFixed(1)} ${u}`,
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
