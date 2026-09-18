---
date_created: 2026-09-18 19:05:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-18 19:05:00
---

# v2.7.2 — Blutdruck-Notizen im Feed sichtbar (2026-09-18)
- `fetch_bp_events()` selektierte bisher nur `systolic`/`diastolic`/`pulse` — die `notes`-Spalte
  wurde nie mitgeladen, obwohl sie in health.bensn.me beim Anlegen einer Messung befüllbar ist
- `bp_reading` in `SERVICE_EVENTS` rendert die Notiz jetzt als zusätzliche Zeile unter den
  Messwerten (`segBody(n.notes)`), analog zu `medication_note`
- Gleicher Fix parallel in health.bensn.mes eigenem Verlauf (siehe dortiges Changelog v1.6.2)
