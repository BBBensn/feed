---
date_created: 2026-09-16 02:33:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-16 02:33:00
---

# v2.0.3 — Health → Feed Integration (2026-09-16)
- Medikamenten-Einnahmen, Blutdruck-Messungen und Mahlzeiten aus `health.bensn.me` erscheinen
  jetzt live in der Feed-Timeline (`medication_taken`, `bp_reading`, `meal_logged`)
- Liest die `health_*`-Tabellen direkt aus Postgres statt über einen internen HTTP-Call
  (anders als beim Worktracker) — feed-api hat über die `shares`-Tabelle ohnehin schon eine
  funktionierende DB-Verbindung, ein zweites Cross-Service-HTTP-Pattern wäre unnötig gewesen
- Nur in `/api/feed/combined` (privat) gemergt — bewusst NICHT in `/api/feed/combined/shared`
  oder `/api/share/<token>`, damit medizinische Daten nie über einen geteilten Link sichtbar
  werden können
- Neue Farbe Teal (`#22d3d3`) + eigener "Health"-Filter-Button für die drei neuen Typen
