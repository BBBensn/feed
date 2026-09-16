---
date_created: 2026-09-16 04:23:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-16 04:23:00
---

# v2.4.0 — Edit/Delete, Bugfixes, editierbarer Zeitpunkt (2026-09-16)
- **Bugfix (Datenverlust-Verdacht, tatsächlich ein Limit-Problem):** Einträge vor dem
  10. Mai fehlten im Feed. Ursache: `/api/feed/combined?limit=500` schneidet den nach
  Datum sortierten Pool aus `journal_entries` (368) + Worktracker-Events (bis zu ~590,
  87 Schichten × bis zu 3 Events + 415 Pausen) + Health-Events hart bei 500 ab — bei
  aktuellem Datenvolumen liegt der Cutoff zufällig um den 10. Mai. Kein Datenverlust,
  alle Daten waren in der DB. Limit auf 5000 angehoben (Frontend-Fetch + Backend-interne
  Fetches), reicht für die aktuelle Datenmenge (März 2026 bis heute) komfortabel
- **Bugfix:** Tags wurden beim Erstellen korrekt gespeichert, aber nirgends angezeigt —
  `renderNote()` hatte nie einen Render-Schritt dafür. Neue `tagsHtml()`-Funktion zeigt
  sie jetzt als Chips (blendet den Typ-Namen selbst aus, z.B. kein "mood"-Chip bei
  Mood-Karten, da der Badge das schon zeigt)
- Sync-Button aus der Toolbar entfernt — war für den jetzt abgeschalteten Obsidian-Git-Sync
- Journal-Einträge haben jetzt "Zeitpunkt ändern" (eigenes Sheet, PATCH `entry_date`) und
  "Löschen" (soft-delete) direkt in der Karte
- Mood- und generisches Compose-Sheet haben ein Zeitpunkt-Feld (Standard: jetzt, aber
  änderbar) — für Einträge, die man erst im Nachhinein festhält
