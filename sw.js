const CACHE = 'bensn-feed-v6';
self.addEventListener('install', e => {
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(['/'])));
});
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  // respondWith MUSS immer ein echtes Response-Objekt bekommen — landet die Kette bei
  // undefined (Netzwerk down UND nichts im Cache, was hier meist zutrifft, da nur '/'
  // vorgecached ist), wirft WebKit/Safari "FetchEvent.respondWith received an error:
  // Returned response is null" und die Seite sieht das als kompletten Fetch-Fehler.
  // Chromium verzeiht das stillschweigend, Safari auf wackligem Mobilfunk nicht.
  e.respondWith(
    fetch(e.request).catch(async () => {
      const cached = await caches.match(e.request);
      return cached || new Response('Offline', { status: 503, statusText: 'Offline' });
    })
  );
});
