// Open-Meteo client — runs entirely in the browser. No API key needed.
// Mirrors src/weahist/clients/* + services/history.py.

const GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search";
const ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive";
const AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality";

const HOURLY_WEATHER = ["temperature_2m", "relative_humidity_2m"];
const DAILY_WEATHER = [
  "temperature_2m_max",
  "temperature_2m_min",
  "temperature_2m_mean",
];
const HOURLY_AQI = ["us_aqi", "pm2_5", "pm10"];

// ---- Range presets ---------------------------------------------------
const RANGE_DAYS = {
  "1d": 1,
  "3d": 3,
  "1w": 7,
  "2w": 14,
  "1m": 30,
  "3m": 90,
  "6m": 180,
  "1y": 365,
};

/** Resolve a preset key into { start, end, granularity }. End = yesterday. */
export function resolveRange(rangeKey) {
  const days = RANGE_DAYS[rangeKey] ?? RANGE_DAYS["1w"];
  const end = new Date();
  end.setDate(end.getDate() - 1);
  const start = new Date(end);
  start.setDate(start.getDate() - (days - 1));
  return {
    start: ymd(start),
    end: ymd(end),
    granularity: days > 30 ? "daily" : "hourly",
  };
}

function ymd(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

// ---- HTTP ------------------------------------------------------------
async function getJson(url, params, signal) {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v != null) qs.set(k, String(v));
  }
  const res = await fetch(`${url}?${qs.toString()}`, { signal });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.reason || body.error || detail;
    } catch { /* ignore */ }
    throw new Error(`Open-Meteo ${url}: ${res.status} ${detail}`);
  }
  return res.json();
}

// ---- Geocoding -------------------------------------------------------
export async function geocode(name, { count = 6, signal } = {}) {
  if (!name || !name.trim()) return [];
  const data = await getJson(
    GEOCODING_URL,
    { name: name.trim(), count, format: "json", language: "en" },
    signal,
  );
  const results = data.results || [];
  return results.map((r) => ({
    name: r.name,
    country: r.country,
    admin1: r.admin1,
    latitude: r.latitude,
    longitude: r.longitude,
    timezone: r.timezone || "UTC",
    label: [r.name, r.admin1, r.country].filter(Boolean).join(", "),
  }));
}

// ---- Archive (weather) ----------------------------------------------
async function fetchArchive(location, start, end, granularity, signal) {
  const params = {
    latitude: location.latitude,
    longitude: location.longitude,
    start_date: start,
    end_date: end,
    timezone: location.timezone,
  };
  let blockKey;
  if (granularity === "hourly") {
    params.hourly = HOURLY_WEATHER.join(",");
    blockKey = "hourly";
  } else {
    params.daily = DAILY_WEATHER.join(",");
    blockKey = "daily";
  }
  const data = await getJson(ARCHIVE_URL, params, signal);
  const block = data[blockKey];
  if (!block || !Array.isArray(block.time)) {
    throw new Error(`archive response missing ${blockKey} block`);
  }
  return { times: block.time, columns: block };
}

// ---- Air quality (always hourly upstream; resampled to daily if needed)
async function fetchAirQuality(location, start, end, granularity, signal) {
  const params = {
    latitude: location.latitude,
    longitude: location.longitude,
    start_date: start,
    end_date: end,
    timezone: location.timezone,
    hourly: HOURLY_AQI.join(","),
  };
  let data;
  try {
    data = await getJson(AIR_QUALITY_URL, params, signal);
  } catch (err) {
    if (err.name === "AbortError") throw err;
    console.warn("air-quality fetch failed; continuing without AQI:", err);
    return { times: [], columns: {} };
  }
  const block = data.hourly;
  if (!block || !Array.isArray(block.time) || block.time.length === 0) {
    return { times: [], columns: {} };
  }
  // For daily, resample by the local-date prefix of each hourly timestamp.
  if (granularity === "daily") {
    return resampleHourlyToDaily(block);
  }
  return { times: block.time, columns: block };
}

function resampleHourlyToDaily(block) {
  const buckets = new Map(); // dateStr -> { count, sums: {col: number} }
  for (let i = 0; i < block.time.length; i++) {
    const dayKey = block.time[i].slice(0, 10); // 'YYYY-MM-DD'
    let bucket = buckets.get(dayKey);
    if (!bucket) {
      bucket = { count: {}, sums: {} };
      for (const col of HOURLY_AQI) {
        bucket.count[col] = 0;
        bucket.sums[col] = 0;
      }
      buckets.set(dayKey, bucket);
    }
    for (const col of HOURLY_AQI) {
      const v = block[col]?.[i];
      if (v != null && Number.isFinite(v)) {
        bucket.sums[col] += v;
        bucket.count[col] += 1;
      }
    }
  }
  const times = [...buckets.keys()].sort();
  const columns = { time: times };
  for (const col of HOURLY_AQI) {
    columns[col] = times.map((d) => {
      const b = buckets.get(d);
      return b.count[col] > 0 ? b.sums[col] / b.count[col] : null;
    });
  }
  return { times, columns };
}

// ---- Combined fetch -------------------------------------------------
/**
 * Fetch + merge weather and AQI for a location and range.
 * Returns { location, start, end, granularity, times, weather, aqi, aqiCoverage }.
 * Times are local to the location (Open-Meteo returns them already in `timezone`).
 */
export async function fetchHistory(location, rangeKey, { signal } = {}) {
  const { start, end, granularity } = resolveRange(rangeKey);

  // Fetch in parallel; AQI failures are absorbed inside fetchAirQuality.
  const [weather, aqi] = await Promise.all([
    fetchArchive(location, start, end, granularity, signal),
    fetchAirQuality(location, start, end, granularity, signal),
  ]);

  // Build AQI lookup keyed by time string for left-join onto weather times.
  const aqiByTime = new Map();
  for (let i = 0; i < aqi.times.length; i++) {
    const row = {};
    for (const col of HOURLY_AQI) row[col] = aqi.columns[col]?.[i] ?? null;
    aqiByTime.set(aqi.times[i], row);
  }

  const weatherCols =
    granularity === "hourly" ? HOURLY_WEATHER : DAILY_WEATHER;

  const merged = {
    times: weather.times,
    weather: {},
    aqi: { us_aqi: [], pm2_5: [], pm10: [] },
  };
  for (const col of weatherCols) {
    merged.weather[col] = weather.columns[col] ?? new Array(weather.times.length).fill(null);
  }

  let aqiPresent = 0;
  for (const t of weather.times) {
    // Match by exact string OR by date prefix (daily-vs-hourly mismatch safeguard).
    const a = aqiByTime.get(t) || aqiByTime.get(t.slice(0, 10)) || null;
    for (const col of HOURLY_AQI) {
      merged.aqi[col].push(a ? a[col] : null);
    }
    if (a && a.us_aqi != null) aqiPresent += 1;
  }

  return {
    location,
    start,
    end,
    granularity,
    times: merged.times,
    weather: merged.weather,
    aqi: merged.aqi,
    aqiCoverage: weather.times.length === 0 ? 0 : aqiPresent / weather.times.length,
  };
}
