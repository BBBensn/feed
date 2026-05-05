const CACHE = 'bensn-wt-v2';
const STATIC = [
  '/shared/bensn.css',
  '/shared/bensn.js',
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(STATIC)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);

  // API calls + navigation: always network, never cache
  if (url.pathname.startsWith('/api/') || e.request.mode === 'navigate') {
    e.respondWith(fetch(e.request));
    return;
  }

  // Shared static files: cache first
  if (url.pathname.startsWith('/shared/')) {
    e.respondWith(
      caches.match(e.request).then(cached => {
        if (cached) return cached;
        return fetch(e.request).then(res => {
          if (res.ok) {
            const clone = res.clone();
            caches.open(CACHE).then(c => c.put(e.request, clone));
          }
          return res;
        });
      })
    );
    return;
  }

  // Everything else: network only
  e.respondWith(fetch(e.request));
});
