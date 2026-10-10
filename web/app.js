// Weather History — pure-static frontend.
// Calls Open-Meteo directly from the browser; no backend required.

import {
  MAX_CUSTOM_DAYS,
  RANGE_KEYS,
  fetchHistory,
  geocode,
  todayYmd,
  validateCustomRange,
} from "./api.js";
import { aqiBand } from "./aqi.js";
import { NARROW_BREAKPOINT, buildCharts, visibleAqiBands } from "./chart.js";
import {
  PLOTLY_VI_LOCALE,
  applyStaticStrings,
  formatDate,
  formatNumber,
  getLang,
  setLang,
  t,
} from "./i18n.js";

const SITE_URL = "https://tnam0x.github.io/weahist/";
const PREFS_KEY = "weahist.prefs.v1";
const DEFAULTS = {
  location: "Hanoi, Vietnam",
  range: "1w", // a RANGE_KEYS entry, or "custom" (uses start/end)
  theme: "system", // "system" | "light" | "dark"
  units: "c", // "c" | "f"
};
const MAX_RECENT = 5;
const FETCH_TIMEOUT_MS = 30_000;
const CITY_MATCH_KM = 10;

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

// ---- Plotly (loaded async so labels and data don't wait for it) ----------
const plotlyReady = new Promise((resolve, reject) => {
  if (window.Plotly) {
    resolve(window.Plotly);
    return;
  }
  const script = document.getElementById("plotly-js");
  script.addEventListener("load", () => resolve(window.Plotly));
  script.addEventListener("error", () => reject(new Error("Plotly failed to load")));
}).then((Plotly) => {
  Plotly.register(PLOTLY_VI_LOCALE);
  return Plotly;
});

// ---- Site pages & routing -------------------------------------------------
// Static pages exist for the places in cities.json (/<slug>/); any other
// place lives on the root page as ?location=…
const SITE_ROOT = new URL(document.documentElement.dataset.root || "./", window.location.href);
const pageCity = JSON.parse(document.getElementById("page-city")?.textContent || "null");
let cities = pageCity ? [pageCity] : [];
const citiesReady = fetch(new URL("cities.json", SITE_ROOT))
  .then((res) => (res.ok ? res.json() : cities))
  .then((list) => {
    cities = list;
    return list;
  })
  .catch(() => cities);

function findCity(slug) {
  return cities.find((c) => c.slug === slug) ?? null;
}

function distanceKm(a, b) {
  const rad = (d) => (d * Math.PI) / 180;
  const dLat = rad(b.latitude - a.latitude);
  const dLon = rad(b.longitude - a.longitude);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(rad(a.latitude)) * Math.cos(rad(b.latitude)) * Math.sin(dLon / 2) ** 2;
  return 12_742 * Math.asin(Math.sqrt(h));
}

/** The city page for a resolved location, if one is close enough. */
function matchCity(loc) {
  if (!loc || loc.mine) return null;
  if (loc.slug) return findCity(loc.slug);
  let best = null;
  for (const city of cities) {
    const d = distanceKm(loc, city);
    if (d <= CITY_MATCH_KM && (!best || d < best.d)) best = { city, d };
  }
  return best?.city ?? null;
}

function cityName(city) {
  return getLang() === "vi" ? city.vi : city.en;
}
function cityCountry(city) {
  return getLang() === "vi" ? city.country_vi : city.country_en;
}

/** A resolved location for a city page. */
function cityLocation(city) {
  const name = cityName(city);
  const country = cityCountry(city);
  return {
    slug: city.slug,
    name,
    country,
    admin1: city.province ?? "",
    latitude: city.latitude,
    longitude: city.longitude,
    timezone: city.timezone,
    label: `${name}, ${country}`,
  };
}

/** Display name for a location, localized when it is a known city. */
function placeName(loc) {
  const city = loc?.slug ? findCity(loc.slug) : null;
  if (city) return `${cityName(city)}, ${cityCountry(city)}`;
  return [loc?.name, loc?.country].filter(Boolean).join(", ");
}

/** The slug of the city page we're on (path below the site root), if any. */
function slugFromPath() {
  const rest = decodeURIComponent(window.location.pathname.slice(SITE_ROOT.pathname.length));
  const slug = rest.replace(/\/(index\.html)?$/, "");
  return slug && !slug.includes("/") ? slug : null;
}

/** Read location/range/units from the current URL into prefs. */
function readUrlState({ initial }) {
  const params = new URLSearchParams(window.location.search);
  const slug = initial ? pageCity?.slug ?? null : slugFromPath();
  const city = slug ? (initial ? pageCity : findCity(slug)) : null;
  if (city) {
    const loc = cityLocation(city);
    prefs.location = loc.label;
    prefs.locationResolved = loc;
  } else if (params.get("location")) {
    prefs.location = params.get("location");
  } else if (!initial) {
    // Back to the bare root page: the remembered place.
    const saved = loadPrefs();
    prefs.location = saved.location;
    prefs.locationResolved = saved.locationResolved;
  }
  prefs.range = params.get("range") || (initial ? prefs.range : DEFAULTS.range);
  delete prefs.start;
  delete prefs.end;
  if (params.get("start") && params.get("end")) {
    prefs.range = "custom";
    prefs.start = params.get("start");
    prefs.end = params.get("end");
  }
  if (initial && params.get("theme")) prefs.theme = params.get("theme");
  if (["c", "f"].includes(params.get("units"))) prefs.units = params.get("units");
  else if (!initial) prefs.units = loadPrefs().units;
  // Fall back to the default preset if the saved/shared range is unusable.
  if (
    prefs.range === "custom"
      ? validateCustomRange(prefs.start, prefs.end) !== null
      : !RANGE_KEYS.includes(prefs.range)
  ) {
    prefs.range = DEFAULTS.range;
  }
}

/** Does the current URL name a place (city page or ?location=)? */
function urlNamesPlace() {
  return Boolean(slugFromPath() || new URLSearchParams(window.location.search).get("location"));
}

/** URL for the current state: /<slug>/ for city pages, otherwise ?location=. */
function stateUrl({ includeTheme = false } = {}) {
  const city = matchCity(selectedLocation);
  const url = city ? new URL(`${city.slug}/`, SITE_ROOT) : new URL(SITE_ROOT);
  const params = url.searchParams;
  if (!city) params.set("location", prefs.location);
  if (prefs.range === "custom") {
    params.set("start", prefs.start);
    params.set("end", prefs.end);
  } else if (prefs.range !== DEFAULTS.range) {
    params.set("range", prefs.range);
  }
  if (prefs.units !== DEFAULTS.units) params.set("units", prefs.units);
  if (includeTheme && prefs.theme !== DEFAULTS.theme) params.set("theme", prefs.theme);
  return url.toString();
}

// "push" when the place changes, "replace" for range/units tweaks.
let pendingNav = null;
function syncUrl(mode) {
  const url = stateUrl();
  if (url === window.location.href) return;
  if (mode === "push") history.pushState(null, "", url);
  else history.replaceState(null, "", url);
}

window.addEventListener("popstate", async () => {
  await citiesReady;
  readUrlState({ initial: false });
  selectedLocation = prefs.locationResolved?.label === prefs.location ? prefs.locationResolved : null;
  locInput.value = prefs.location;
  syncRangeUI();
  syncUnitsUI();
  closeCustomForm();
  refreshChart();
});

/** Title, description, canonical and intro for the current URL and place. */
function updatePageMeta() {
  const city = slugFromPath() ? findCity(slugFromPath()) : null;
  const named = urlNamesPlace() && lastHistory;
  const place = named ? placeName(lastHistory.location) : null;
  document.title = place ? t("meta.titleCity", { place }) : t("meta.title");
  const description = document.querySelector('meta[name="description"]');
  if (description) {
    description.content = place ? t("intro.city", { place }) : t("meta.description");
  }
  const canonical = document.querySelector('link[rel="canonical"]');
  if (canonical) canonical.href = city ? `${SITE_URL}${city.slug}/` : SITE_URL;
  introEl.textContent = place ? t("intro.city", { place }) : t("intro.root");
}

readUrlState({ initial: true });

// ---- Language -----------------------------------------------------------
const langToggle = document.getElementById("lang-toggle");
function applyLanguage() {
  applyStaticStrings();
  // Footer city links carry both names from the site build.
  for (const a of document.querySelectorAll(".city-index a[data-vi]")) {
    a.textContent = a.dataset[getLang()];
  }
  const other = getLang() === "vi" ? "en" : "vi";
  langToggle.textContent = other.toUpperCase();
  langToggle.lang = other;
}
langToggle.addEventListener("click", () => {
  setLang(getLang() === "vi" ? "en" : "vi");
  applyLanguage();
  if (selectedLocation?.slug) {
    const city = findCity(selectedLocation.slug);
    if (city) {
      selectedLocation = cityLocation(city);
      prefs.location = selectedLocation.label;
      prefs.locationResolved = selectedLocation;
      locInput.value = prefs.location;
      savePrefs(prefs);
    }
  }
  if (lastHistory) {
    lastHistory = { ...lastHistory, location: selectedLocation ?? lastHistory.location };
    renderAll(lastHistory);
  }
  updatePageMeta();
});
applyLanguage();

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
        title: card.querySelector(".card-title"),
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
const introEl = document.getElementById("page-intro");
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
  pendingNav = pendingNav ?? "replace";
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
  customError.textContent = error ? t(`custom.${error}`, { max: MAX_CUSTOM_DAYS }) : "";
  if (error) return;
  prefs.range = "custom";
  prefs.start = customStart.value;
  prefs.end = customEnd.value;
  savePrefs(prefs);
  syncRangeUI();
  closeCustomForm();
  pendingNav = pendingNav ?? "replace";
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
    : t(`range.${prefs.range}`);
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
    syncUrl("replace");
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
    showErrorBanner(t("error.geoUnsupported"));
    return;
  }
  locateBtn.setAttribute("aria-busy", "true");
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      locateBtn.removeAttribute("aria-busy");
      const { latitude, longitude } = pos.coords;
      const name = t("location.mine");
      useLocation({
        mine: true,
        name,
        country: "",
        admin1: "",
        latitude,
        longitude,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
        label: `${name} (${latitude.toFixed(2)}, ${longitude.toFixed(2)})`,
      });
    },
    (err) => {
      locateBtn.removeAttribute("aria-busy");
      const reason =
        err.code === err.PERMISSION_DENIED
          ? t("error.geo.denied")
          : err.code === err.TIMEOUT
          ? t("error.geo.timeout")
          : t("error.geo.unavailable");
      showErrorBanner(t("error.geo", { reason }));
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
  pendingNav = "push";
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
let acHeading = null; // e.g. "Recent" above the list

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
    acResults = await geocode(q, { count: 6, signal: ctrl.signal, language: getLang() });
    acHeading = null;
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
  const items = acResults.map((r, i) => {
    const li = el("li", i === acActive ? "active" : "", r.label);
    li.dataset.idx = String(i);
    li.setAttribute("role", "option");
    li.setAttribute("aria-selected", String(i === acActive));
    return li;
  });
  if (acHeading) {
    const head = el("li", "suggestions-head", acHeading);
    head.setAttribute("role", "presentation");
    items.unshift(head);
  }
  suggestionsEl.replaceChildren(...items);
  suggestionsEl.hidden = false;
  locInput.setAttribute("aria-expanded", "true");
}
function hideSuggestions() {
  suggestionsEl.hidden = true;
  suggestionsEl.replaceChildren();
  acActive = -1;
  locInput.setAttribute("aria-expanded", "false");
}
function showRecent() {
  if (acAbort) acAbort.abort();
  acResults = prefs.recent || [];
  acHeading = t("location.recent");
  acActive = -1;
  renderSuggestions();
}
function pickSuggestion(idx) {
  const r = acResults[idx];
  if (r) useLocation(r);
}

function submitFreeText() {
  prefs.location = locInput.value.trim();
  delete prefs.locationResolved;
  savePrefs(prefs);
  hideSuggestions();
  selectedLocation = null;
  pendingNav = "push";
  refreshChart();
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
    if (e.key === "Enter") submitFreeText();
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
    else submitFreeText();
  } else if (e.key === "Escape") {
    hideSuggestions();
  }
});

suggestionsEl.addEventListener("mousedown", (e) => {
  const li = e.target.closest("li[data-idx]");
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
  delete prefs.locationResolved;
  delete prefs.recent;
  locInput.value = prefs.location;
  themeSelect.value = prefs.theme;
  syncRangeUI();
  syncUnitsUI();
  closeCustomForm();
  selectedLocation = null;
  applyTheme();
  pendingNav = "push";
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
let lastHistory = null; // cached for cheap theme/language/unit re-renders
let selectedLocation =
  prefs.locationResolved && prefs.locationResolved.label === prefs.location
    ? prefs.locationResolved
    : null;

async function rerenderChartIfData() {
  if (lastHistory) await renderCharts(lastHistory);
}

function renderAll(history) {
  renderHeading(history);
  renderKpis(history);
  return renderCharts(history);
}

function cardSubtitle(key, history) {
  const daily = history.granularity === "daily";
  if (key === "aqi") return daily ? t("card.aqiDaily") : t("card.hourly", { unit: "US AQI" });
  const unit = key === "temperature" ? history.tempUnit : "%";
  return t(daily ? "card.dailyBand" : "card.hourly", { unit });
}

async function renderCharts(rawHistory) {
  const history = withUnits(rawHistory);
  const figs = buildCharts(history, effectiveTheme());
  const Plotly = await plotlyReady;
  const config = plotlyConfig();
  await Promise.all(
    CHART_KEYS.map(async (key) => {
      const c = cards[key];
      const fig = figs[key];
      c.sub.textContent = cardSubtitle(key, history);
      c.toggle.textContent = t(c.toggle.getAttribute("aria-pressed") === "true" ? "card.chart" : "card.table");
      if (c.legend) renderBandLegend(c.legend, fig ? history.aqi.us_aqi : null);
      c.empty.hidden = Boolean(fig);
      c.toggle.hidden = !fig;
      c.png.hidden = !fig;
      if (!fig) {
        c.empty.textContent = t(`empty.${key}`);
        c.wrap.hidden = true;
        c.table.hidden = true;
        Plotly.purge(c.chart);
        return;
      }
      const showTable = c.toggle.getAttribute("aria-pressed") === "true";
      c.wrap.hidden = showTable;
      c.table.hidden = !showTable;
      if (showTable) renderTable(key, rawHistory);
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
      item.append(swatch, document.createTextNode(t(`aqi.${band.key}`)));
      return item;
    }),
  );
  listEl.hidden = false;
}

// ---- Table view (the accessible twin of each chart) ---------------------
function tableColumns(key, history) {
  const w = history.weather;
  const unit = history.tempUnit;
  const daily = history.granularity === "daily";
  if (key === "temperature") {
    return daily
      ? [
          [t("table.low", { unit }), w.temperature_2m_min, 1],
          [t("table.mean", { unit }), w.temperature_2m_mean, 1],
          [t("table.high", { unit }), w.temperature_2m_max, 1],
        ]
      : [[t("table.temperature", { unit }), w.temperature_2m, 1]];
  }
  if (key === "humidity") {
    return daily
      ? [
          [t("table.low", { unit: "%" }), w.relative_humidity_2m_min, 0],
          [t("table.mean", { unit: "%" }), w.relative_humidity_2m_mean, 0],
          [t("table.high", { unit: "%" }), w.relative_humidity_2m_max, 0],
        ]
      : [[t("table.humidity"), w.relative_humidity_2m, 0]];
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
  table.setAttribute("aria-label", t("table.aria", { title: cards[key].title.textContent }));
  const headRow = el("tr");
  headRow.append(el("th", null, t(history.granularity === "daily" ? "table.date" : "table.time")));
  for (const [label] of columns) headRow.append(el("th", null, label));
  const head = el("thead");
  head.append(headRow);
  table.append(head);
  const body = el("tbody");
  history.times.forEach((time, i) => {
    const row = el("tr");
    row.append(el("td", null, time.replace("T", " ")));
    for (const [, values, digits] of columns) {
      const v = values?.[i];
      row.append(el("td", null, v == null || !Number.isFinite(v) ? "—" : formatNumber(v, digits)));
    }
    body.append(row);
  });
  table.append(body);
  cards[key].table.replaceChildren(table);
}

for (const key of CHART_KEYS) {
  const c = cards[key];
  c.toggle.addEventListener("click", async () => {
    const show = c.toggle.getAttribute("aria-pressed") !== "true";
    c.toggle.setAttribute("aria-pressed", String(show));
    c.toggle.textContent = t(show ? "card.chart" : "card.table");
    if (show && lastHistory) renderTable(key, lastHistory);
    c.table.hidden = !show;
    c.wrap.hidden = show;
    if (!show && c.chart._fullLayout) (await plotlyReady).Plots.resize(c.chart);
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

shareBtn.addEventListener("click", async () => {
  await citiesReady;
  const url = stateUrl({ includeTheme: true });
  const coarse = window.matchMedia("(pointer: coarse)").matches;
  if (coarse && navigator.share) {
    try {
      await navigator.share({ title: "Weather History", url });
    } catch (err) {
      if (err.name !== "AbortError") showToast(t("toast.shareFailed"));
    }
    return;
  }
  try {
    await navigator.clipboard.writeText(url);
    showToast(t("toast.copied"));
  } catch {
    showToast(t("toast.copyFailed"));
    history.replaceState(null, "", url);
  }
});

function fileSlug(history) {
  const place = (history.location.slug || history.location.name || "location")
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/đ/g, "d")
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
  history.times.forEach((time, i) => {
    lines.push([time, ...columns.map(([, values]) => round(values?.[i]))].map(csvCell).join(","));
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
  cards[key].png.addEventListener("click", async () => {
    const c = cards[key];
    if (!lastHistory || !c.chart._fullLayout) return;
    (await plotlyReady).downloadImage(c.chart, {
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
      for (const other of otherCharts(div)) window.Plotly.Fx.hover(other, { xval: ev.xvals[0] });
    } finally {
      syncing = false;
    }
  });
  div.on("plotly_unhover", () => {
    if (syncing) return;
    syncing = true;
    try {
      for (const other of otherCharts(div)) window.Plotly.Fx.unhover(other);
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
    Promise.all(otherCharts(div).map((other) => window.Plotly.relayout(other, update))).finally(
      () => {
        syncing = false;
      },
    );
  });
}

function plotlyConfig() {
  const hasHover = window.matchMedia("(hover: hover)").matches;
  return {
    responsive: true,
    displaylogo: false,
    displayModeBar: hasHover ? "hover" : false,
    modeBarButtonsToRemove: ["lasso2d", "select2d"],
    locale: getLang() === "vi" ? "vi" : "en",
  };
}

async function refreshChart() {
  const locText = (prefs.location || "").trim();
  if (!locText) {
    statusEl.textContent = t("status.enter");
    return;
  }

  // Only the first load gets a status line; refetches keep the previous
  // render (dimmed) so nothing jumps.
  if (!lastHistory) {
    statusEl.textContent = t("status.loading", { place: locText, range: currentRangeLabel() });
  }
  hideErrorBanner();

  if (inFlight) inFlight.abort();
  const ctrl = new AbortController();
  inFlight = ctrl;
  const nav = pendingNav;
  pendingNav = null;
  const timer = setTimeout(
    () => ctrl.abort(new DOMException("timeout", "TimeoutError")),
    FETCH_TIMEOUT_MS,
  );
  setLoading(true);

  try {
    let location = selectedLocation;
    if (!location || location.label !== locText) {
      const language = getLang();
      let matches = await geocode(locText, { count: 1, signal: ctrl.signal, language });
      // Saved labels can include admin1 (e.g. "Hanoi, Hanoi, Vietnam")
      // which the geocoder doesn't match — retry with the leading segment.
      if (matches.length === 0 && locText.includes(",")) {
        const head = locText.split(",")[0].trim();
        if (head) {
          matches = await geocode(head, { count: 1, signal: ctrl.signal, language });
        }
      }
      if (matches.length === 0) throw new Error(t("error.noMatch", { q: locText }));
      location = { ...matches[0], label: locText };
    }
    await citiesReady;
    const city = matchCity(location);
    if (city) {
      // Known places get their canonical, localized name everywhere.
      location = cityLocation(city);
      prefs.location = location.label;
      locInput.value = location.label;
    }
    selectedLocation = location;
    prefs.locationResolved = location;
    savePrefs(prefs);

    const history = await fetchHistory(location, currentRange(), {
      signal: ctrl.signal,
    });
    lastHistory = history;
    rememberLocation(location);
    statusEl.textContent = "";
    if (nav) syncUrl(nav);
    csvBtn.hidden = false;
    await renderAll(history);
    updatePageMeta();
    if (nav === "push") countPageview();
  } catch (err) {
    if (err.name === "AbortError" && ctrl.signal.reason?.name !== "TimeoutError") {
      return; // superseded by a newer request
    }
    const msg =
      err.name === "AbortError" || err.name === "TimeoutError"
        ? t("error.timeout", { s: FETCH_TIMEOUT_MS / 1000 })
        : t("error.fetch", { detail: err.message });
    statusEl.textContent = "";
    showErrorBanner(msg);
  } finally {
    clearTimeout(timer);
    if (inFlight === ctrl) inFlight = null;
    setLoading(false);
  }
}

// ---- Heading & KPI tiles -------------------------------------------------
function renderHeading(history) {
  const { location, start, end, granularity } = history;
  placeTitleEl.textContent = placeName(location);
  const range = start === end ? formatDate(start) : `${formatDate(start)} – ${formatDate(end)}`;
  rangeSubtitleEl.textContent = `${range} · ${t(`granularity.${granularity}`)} · ${location.timezone}`;
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
          t("kpi.temperature"),
          `${formatNumber(temp.avg, 1)} ${u}`,
          `${t("kpi.lowHigh", { low: formatNumber(temp.low, 1), high: formatNumber(temp.high, 1) })} ${u}`,
        )
      : kpiTile("temperature", t("kpi.temperature"), "—", t("kpi.noData")),
  );

  const humid = stats(history.weather, "relative_humidity_2m", "relative_humidity_2m");
  tiles.push(
    humid
      ? kpiTile(
          "humidity",
          t("kpi.humidity"),
          `${formatNumber(humid.avg, 0)}%`,
          `${t("kpi.lowHigh", { low: formatNumber(humid.low, 0), high: formatNumber(humid.high, 0) })}%`,
        )
      : kpiTile("humidity", t("kpi.humidity"), "—", t("kpi.noData")),
  );

  const aqis = finite(history.aqi.us_aqi);
  if (aqis.length) {
    const peak = Math.max(...aqis);
    const band = aqiBand(peak);
    const value = document.createDocumentFragment();
    const badge = el("span", "aqi-badge");
    const dot = el("span", "aqi-dot");
    dot.style.background = band.color;
    badge.append(dot, document.createTextNode(t(`aqi.${band.key}`)));
    value.append(document.createTextNode(formatNumber(peak, 0)), badge);
    tiles.push(kpiTile("aqi", t("kpi.aqi"), value, t(`aqi.${band.key}.advice`)));
  } else {
    tiles.push(kpiTile("aqi", t("kpi.aqi"), "—", t("kpi.noAqi")));
  }

  const n = history.times.length;
  tiles.push(
    kpiTile(
      "coverage",
      t("kpi.coverage"),
      `${formatNumber(history.aqiCoverage * 100, 0)}%`,
      t(`kpi.readings.${history.granularity}`, { n }),
    ),
  );

  kpisEl.replaceChildren(...tiles);
  kpisEl.hidden = false;
}

// ---- Analytics ------------------------------------------------------------
/** GoatCounter only counts full page loads; count in-app place changes too. */
function countPageview() {
  const url = new URL(window.location.href);
  window.goatcounter?.count?.({ path: url.pathname + url.search, title: document.title });
}

// ---- Offline support ----------------------------------------------------
const offlineBanner = document.getElementById("offline-banner");
function syncOnline() {
  offlineBanner.hidden = navigator.onLine;
}
window.addEventListener("online", () => {
  syncOnline();
  if (!lastHistory) refreshChart();
});
window.addEventListener("offline", syncOnline);
syncOnline();

if ("serviceWorker" in navigator) {
  navigator.serviceWorker
    .register(new URL("sw.js", SITE_ROOT), { scope: SITE_ROOT.pathname })
    .catch(() => {
      /* unsupported or blocked: the app works without it */
    });
}

// Initial render.
refreshChart();

// Re-render charts on viewport size / orientation changes so the
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
