const CACHE_NAME = 'dip-reserve-v3';
const ASSETS = ['./index.html', './manifest.json', './icon-192.png', './icon-512.png'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(names.filter((n) => n !== CACHE_NAME).map((n) => caches.delete(n)))
    )
  );
  self.clients.claim();
});

// Network-first for the HTML page AND all JSON data files (price data, fundamentals,
// NSE list, watchlist, cross-device state) -- these must always be fresh. Only the
// icons stay cache-first, since those genuinely never change.
// Falls back to cache only when there's no network at all (offline use).
self.addEventListener('fetch', (event) => {
  const url = event.request.url;
  const isHTML = event.request.mode === 'navigate' || url.endsWith('.html');
  const isJSON = url.endsWith('.json');
  const networkFirst = isHTML || isJSON;

  if (networkFirst) {
    event.respondWith(
      fetch(event.request, { cache: 'no-store' })
        .then((res) => {
          const clone = res.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          return res;
        })
        .catch(() => caches.match(event.request))
    );
  } else {
    event.respondWith(
      caches.match(event.request).then((cached) => cached || fetch(event.request))
    );
  }
});
