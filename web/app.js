// Weather History — pure-static frontend.
// Calls Open-Meteo directly from the browser; no backend required.

import { geocode, fetchHistory } from "./api.js";
import { buildFigure } from "./chart.js";

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

// ---- Controls ---------------------------------------------------------
const locInput = document.getElementById("location-input");
const rangeSelect = document.getElementById("range-select");
const suggestionsEl = document.getElementById("location-suggestions");
const statusEl = document.getElementById("status");
const chartEl = document.getElementById("chart");
const summaryEl = document.getElementById("summary");
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
let selectedLocation = null; // resolved Location from autocomplete

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
  if (!lastHistory) return;
  await Plotly.react(
    chartEl,
    ...Object.values(buildFigure(lastHistory, effectiveTheme())),
    plotlyConfig(),
  );
}

function plotlyConfig() {
  return {
    responsive: true,
    displaylogo: false,
    modeBarButtonsToRemove: ["lasso2d", "select2d"],
  };
}

async function refreshChart() {
  const locText = (prefs.location || "").trim();
  if (!locText) {
    statusEl.textContent = "Enter a location to begin.";
    return;
  }

  statusEl.textContent = `Loading ${locText} (${rangeLabel(prefs.range)})…`;
  hideErrorBanner();
  summaryEl.hidden = true;

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
      const matches = await geocode(locText, { count: 1, signal: ctrl.signal });
      if (matches.length === 0) throw new Error(`No matches for "${locText}"`);
      location = matches[0];
      selectedLocation = location;
    }
    const history = await fetchHistory(location, prefs.range, {
      signal: ctrl.signal,
    });
    lastHistory = history;
    const fig = buildFigure(history, effectiveTheme());
    await Plotly.react(chartEl, fig.data, fig.layout, plotlyConfig());
    statusEl.textContent = "";
    renderSummary(history);
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

function renderSummary(history) {
  const tempCol =
    "temperature_2m" in history.weather
      ? "temperature_2m"
      : "temperature_2m_mean";
  const temps = (history.weather[tempCol] || []).filter((v) => v != null && Number.isFinite(v));
  const aqis = (history.aqi.us_aqi || []).filter((v) => v != null && Number.isFinite(v));

  const items = [
    ["Granularity", history.granularity],
    ["Observations", String(history.times.length)],
  ];
  if (temps.length) {
    items.push(["Max temp", `${Math.max(...temps).toFixed(1)} °C`]);
    items.push(["Min temp", `${Math.min(...temps).toFixed(1)} °C`]);
  }
  if (aqis.length) {
    items.push(["Peak AQI", `${Math.max(...aqis).toFixed(0)}`]);
    items.push(["AQI coverage", `${(history.aqiCoverage * 100).toFixed(0)}%`]);
  }
  summaryEl.innerHTML = items
    .map(
      ([label, value]) =>
        `<div class="summary-item"><span class="summary-label">${escapeHtml(label)}</span><span class="summary-value">${escapeHtml(value)}</span></div>`,
    )
    .join("");
  summaryEl.hidden = false;
}

// Initial render.
refreshChart();
