// THE OFFLINE COPY: a service worker that keeps every file of the map (offline.json lists them: the page, its libraries,
// the light line layers and the point layers) in the browser and answers from there -- so the map opens with no network
// at all, and without downloading its data again. It never updates on its own: the page checks for a newer version and
// offers it (index.html, OFFLINE), and it is fetched only when Update is pressed, into a new cache, the old one dropped
// once the new one is whole. (The same scheme as the language trainer's, apps/multiverse/lang/sw.js.)
//
//   caches: "map-<version>" -- the one in use (the newest whole one)

const PREFIX = "map-";

// first visit: nothing kept yet -- keep the version that is online now
self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil((async () => {
    if ((await caches.keys()).some((k) => k.startsWith(PREFIX))) return;
    const manifest = await (await fetch("offline.json", { cache: "no-store" })).json();
    const name = PREFIX + manifest.version, cache = await caches.open(name);
    try { await cache.addAll(manifest.files.map((f) => new Request(f, { cache: "reload" }))); } catch (error) { await caches.delete(name); throw error; }   // (a file missing online: no copy, tried again next visit)
  })());
});
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

// every request the map makes: the kept copy if there is one (a query string ignored; the folder itself is its
// index.html), else the network
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== location.origin) return;
  if (event.request.cache === "no-store" || event.request.cache === "reload") return;   // (the update asking the network itself)
  event.respondWith((async () => {
    const req = url.pathname.endsWith("/") ? new Request(url.origin + url.pathname + "index.html") : event.request;
    const keys = (await caches.keys()).filter((k) => k.startsWith(PREFIX));
    for (const k of keys.reverse()) {   // (the newest first: during an update both may be there for a moment)
      const hit = await (await caches.open(k)).match(req, { ignoreSearch: true });
      if (hit) return hit;
    }
    return fetch(event.request);
  })());
});
