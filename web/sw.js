// Service worker: makes the app installable and usable offline.
//
// - Pages (HTML):      network first, cached copy when offline.
// - App files:         served from cache, refreshed in the background.
// - Plotly (CDN):      cache first (the URL is versioned).
// - Open-Meteo data:   network first, last good response when offline.
//
// BUILD_ID is replaced by scripts/build_site.py with a hash of the site, so
// each deploy installs fresh caches and drops the old ones.

const BUILD_ID = "dev";
const SHELL_CACHE = `weahist-shell-${BUILD_ID}`;
const DATA_CACHE = "weahist-data-v1";
const DATA_MAX_ENTRIES = 80;
const PLOTLY_URL = "https://cdn.plot.ly/plotly-basic-2.35.2.min.js";

const SHELL_FILES = [
  "./",
  "styles.css",
  "app.js",
  "api.js",
  "chart.js",
  "aqi.js",
  "theme.js",
  "i18n.js",
  "cities.json",
  "favicon.svg",
  "site.webmanifest",
  "icon-192.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(SHELL_CACHE);
      await cache.addAll(SHELL_FILES);
      // Cross-origin script without CORS: an opaque response is fine for <script>.
      try {
        await cache.put(PLOTLY_URL, await fetch(PLOTLY_URL, { mode: "no-cors" }));
      } catch {
        /* cached on first use instead */
      }
      await self.skipWaiting();
    })(),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const keep = new Set([SHELL_CACHE, DATA_CACHE]);
      for (const key of await caches.keys()) {
        if (key.startsWith("weahist-") && !keep.has(key)) await caches.delete(key);
      }
      await self.clients.claim();
    })(),
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;
  const url = new URL(request.url);

  if (request.mode === "navigate") {
    event.respondWith(networkFirst(request, SHELL_CACHE, { fallback: "./" }));
  } else if (url.hostname.endsWith("open-meteo.com")) {
    event.respondWith(networkFirst(request, DATA_CACHE, { trim: DATA_MAX_ENTRIES }));
  } else if (url.href === PLOTLY_URL) {
    event.respondWith(cacheFirst(request, SHELL_CACHE));
  } else if (url.origin === self.location.origin) {
    event.respondWith(staleWhileRevalidate(request, SHELL_CACHE, event));
  }
});

async function networkFirst(request, cacheName, { fallback, trim } = {}) {
  const cache = await caches.open(cacheName);
  try {
    const response = await fetch(request);
    if (response.ok) {
      await cache.put(request, response.clone());
      if (trim) await trimCache(cache, trim);
    }
    return response;
  } catch (err) {
    const cached =
      (await cache.match(request, { ignoreVary: true })) ??
      (fallback ? await caches.match(new URL(fallback, self.registration.scope)) : undefined);
    if (cached) return cached;
    throw err;
  }
}

async function cacheFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response.ok || response.type === "opaque") await cache.put(request, response.clone());
  return response;
}

async function staleWhileRevalidate(request, cacheName, event) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request, { ignoreSearch: true });
  const refresh = fetch(request)
    .then(async (response) => {
      if (response.ok) await cache.put(request, response.clone());
      return response;
    })
    .catch(() => undefined);
  if (cached) {
    event.waitUntil(refresh);
    return cached;
  }
  return (await refresh) ?? Response.error();
}

/** Keep the newest `max` entries (Cache keys come back in insertion order). */
async function trimCache(cache, max) {
  const keys = await cache.keys();
  for (const key of keys.slice(0, Math.max(0, keys.length - max))) await cache.delete(key);
}
