---
date_created: 2026-09-19 18:04:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-19 18:04:00
---

# v2.7.3 — Service-Worker-Bug auf Safari/Mobilfunk behoben (2026-09-19)
- Symptom: am Handy (Safari, sowohl Tab als auch installierte Webapp) zeigte der Feed
  "Verbindungsfehler — FetchEvent.respondWith received an error: Returned response is
  null." — am MacBook (Chromium-basiert) trat der Fehler nicht auf
- Ursache: `sw.js`s Fetch-Handler war `e.respondWith(fetch(e.request).catch(() =>
  caches.match(e.request)))`. Schlägt der echte Netzwerk-Request fehl (auf Mobilfunk
  deutlich wahrscheinlicher als auf stabilem WLAN) UND der Cache hat nichts Passendes
  (der Cache enthält seit `install` nur `/`, sonst nichts), resolved die Kette zu
  `undefined`. `respondWith` MUSS aber ein echtes Response-Objekt bekommen — WebKit/Safari
  wirft dann exakt diesen fatalen Fehler, Chromium verzeiht das offenbar stillschweigend
- Bei `feed` besonders sichtbar, weil der Service Worker hier (anders als bei `health`/
  `tracking`) auch `/api/`-GET-Requests abfängt — ein Hänger bei `/api/feed/combined`
  (großer Response, `limit=5000`) auf Mobilfunk reichte für den kompletten Ausfall
- Fix: Cache-Fallback gibt jetzt immer ein echtes `Response`-Objekt zurück, im
  Worst-Case eine explizite 503-Antwort statt `undefined`
- `CACHE`-Version auf `v6` erhöht, damit alte Service-Worker-Instanzen ersetzt werden
- Identischer Fix gleichzeitig in `health.bensn.me` und `tracking.bensn.me` — alle drei
  Apps hatten denselben `sw.js`-Code kopiert
