---
date_created: 2026-09-16 02:51:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-16 02:51:00
---

# v2.2.0 — Compose-UI für alle 9 Journal-Typen (2026-09-16)
- "+"-Button öffnet jetzt einen Typ-Picker (alle 9 Typen, korrekt eingefärbt), der zu Mood
  (bestehendes Sheet) oder einem neuen generischen Eintrags-Formular routet
- Generisches Formular deckt Diary, Reflexion, Symptome, Therapie, Fits, Arbeit, Ideas,
  Project Log ab: Titel, Tags, Body-Textarea, 0-2 typ-spezifische Zusatzfelder (Text/Select/
  Zahl/Toggle/Tags je nach Typ, definiert in `ENTRY_TYPE_CONFIG`)
- Strukturierte Typen (Symptome, Therapie, Arbeit, Ideas, Project Log) bekommen die
  Original-Markdown-Überschriften als Vorlage im Body vorausgefüllt (z.B. "## Was / Kontext
  / Verlauf / Maßnahmen" für Symptome) — entspricht den bisherigen Obsidian-Templates
- Fits erlaubt Bild-Upload direkt im Formular über den bestehenden `/api/upload`-Endpoint
  (bisher nur extern per iOS Shortcut nutzbar)
- Obsidian wird für neue Einträge in KEINEM Typ mehr gebraucht — offen bleibt nur noch die
  Migration der historischen Notes der übrigen 8 Typen und das Abschalten des Git-Sync
