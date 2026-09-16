---
date_created: 2026-09-17 00:22:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-17 00:22:00
---

# v2.6.0 — Tracking-Integration: Konsum-Events im Feed (2026-09-17)
- Neue `fetch_tracking_events()` in `api/app.py`, liest `tracking_entries` direkt aus
  Postgres (gleiches Muster wie die Health-Integration) — nur `entry_type = 'zaehler'`
  (Konsum-/Zähler-Momente wie Red Bull, Zigarette, Ofen, Weed) wird als Feed-Event gezeigt.
  Vorrat-Buchhaltung (`auffuellung`/`entnahme`/`delta`) bleibt bewusst außen vor — das sind
  keine "Momente", seit tracking v1.6.0 ohnehin nur noch Hintergrundfunktion
- Neuer Event-Typ `tracking_logged`: eigener Filter-Chip "Tracking", eigene Akzentfarbe
  `--c-tracking` (Lime `#a3e635`, passend zu tracking.bensn.mes Farbe auf der Landing-Page)
- Nur im privaten `feed_combined()` gemergt, NICHT in den beiden Shared-Varianten — Konsumdaten
  sind genauso privat wie Medikamente/Blutdruck
