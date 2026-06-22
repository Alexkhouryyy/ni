// JARVIS Mobile — Service Worker
// Caches app shell for offline/installability

const CACHE = "jarvis-mobile-v1";
const SHELL = ["/", "/index.html", "/src/main.ts", "/manifest.json"];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(SHELL)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (e) => {
  // Network-first for API/WS, cache-first for app shell
  if (e.request.url.includes("/api/") || e.request.url.includes("/ws/")) return;
  e.respondWith(
    fetch(e.request).catch(() => caches.match(e.request))
  );
});
