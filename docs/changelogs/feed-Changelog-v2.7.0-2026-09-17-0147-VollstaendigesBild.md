---
date_created: 2026-09-17 01:47:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-17 01:47:00
---

# v2.7.0 — Fehlende Datenquellen + Event-Registry (2026-09-17)
- **Medikamenten-Anmerkungen** (`health_medication_effect_notes`) erscheinen jetzt im Feed —
  bisher tauchte nur die Einnahme selbst auf, nicht die zeitgestempelte Wirkungs-/
  Nebenwirkungsbeobachtung danach, obwohl die für "wie hat das Medikament gewirkt" das
  eigentlich Wichtige ist
- **Gewicht** (`health_weight_logs`) erscheint jetzt im Feed
- **Oura Schlaf** erscheint jetzt im Feed (Score, Dauer, Effizienz), Event-Zeitpunkt =
  Aufwachzeit (`bedtime_end`), nicht Einschlafzeit
- **Oura Herzfrequenz** erscheint als **eine Tages-Zusammenfassung pro Tag** (Ruhepuls,
  Min–Max) statt der rohen ~2000 Samples/Tag — ein kontinuierlicher Datenstrom ist kein
  "Moment" und würde den Feed fluten
- Neuer Filter-Chip "Oura" (eigene Gruppe für Schlaf + Herzfrequenz, eigene Akzentfarbe)
- **Event-Typ-Registry eingeführt** (`SERVICE_EVENTS` im Frontend, `PRIVATE_EVENT_FETCHERS`
  im Backend): vorher musste jeder neue Event-Typ an 8 verstreuten Stellen einzeln
  eingetragen werden (Fetch-Funktion, `feed_combined()`-Wiring, CSS-Farbe, Filter-Button,
  zwei JS-Maps, Render-Dispatch, Filter-Matcher) — genau deshalb fehlten die drei obigen
  Quellen so lange. Ein neuer Typ innerhalb einer bestehenden Gruppe ist jetzt eine
  Registry-Zeile, Farben/Badges/Filter-Matching werden daraus automatisch abgeleitet
- Alle vier neuen Quellen nur im privaten `feed_combined()`, nicht im geteilten Feed-Link
