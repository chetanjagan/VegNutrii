/* VegNutri service worker: caches static assets; pages always come from the network. */
const CACHE = "vegnutri-v4";
const ASSETS = ["/static/css/style.css", "/static/js/main.js", "/static/icons/icon-192.png", "/static/icons/logo.svg",
  "/static/fonts/bricolage-grotesque-latin-800-normal.woff2", "/static/fonts/atkinson-hyperlegible-latin-400-normal.woff2"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  if (url.pathname.startsWith("/static/")) {
    e.respondWith(caches.match(e.request).then((hit) => hit || fetch(e.request).then((res) => {
      const copy = res.clone();
      caches.open(CACHE).then((c) => c.put(e.request, copy));
      return res;
    })));
    return;
  }
  if (e.request.mode === "navigate") {
    e.respondWith(fetch(e.request).catch(() => new Response(
      "<!doctype html><meta name=viewport content='width=device-width'><title>Offline</title>" +
      "<body style='font-family:system-ui;padding:2rem;max-width:32rem'><h1>You're offline</h1>" +
      "<p>VegNutri needs a connection to load this page. Check your internet and try again.</p></body>",
      { headers: { "Content-Type": "text/html" } })));
  }
});
