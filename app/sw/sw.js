// Service worker (tech-spec C7). The build prepends VERSION and FILES: every app and data file in
// this deploy. It caches only the site's own public files, never anything the voter enters.
/* global VERSION, FILES */
const CACHE = `ballot-explorer-${VERSION}`;

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(FILES)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith("ballot-explorer-") && k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  // The page itself is always "/" (hash routes); serve it for any navigation.
  const key = req.mode === "navigate" ? "/" : url.pathname;
  event.respondWith(
    caches.open(CACHE).then((c) => c.match(key)).then((hit) => hit || fetch(req)),
  );
});
