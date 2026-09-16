---
date_created: 2026-09-16 02:46:15
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-16 02:46:15
---

# v2.1.0 — Natives Mood-Compose + journal_entries (2026-09-16)
- Neues `journal_entries`-Schema (Postgres) — erste Phase der Obsidian-Ablösung. Ein Typ-
  diskriminiertes Schema mit `fields` JSONB für typ-spezifische Struktur (analog zum
  bewährten `tracking_entries`-Muster), statt 9 einzelner Tabellen
- Feed bekommt erstmals ein natives Eingabe-Interface: "+"-Button öffnet ein Apple-Journal-
  artiges Mood-Check-in (Valenz-Slider -100..100, Zusammenhang-/Beschreibung-Multiselect mit
  den echten Tag-Listen aus der ModalForms-Config — 18 bzw. 38 Optionen — Tagesreflexion-
  Toggle, Freitext)
- `/api/feed/combined` (+ beide Shared-Varianten) mergen `journal_entries` jetzt zusätzlich zu
  Obsidian-Notes, Worktracker- und Health-Events
- Neue Mood-Card-Visualisierung: divergierender Valenz-Balken (rot/grün von der Mitte aus) +
  Tag-Chips, statt nur Freitext — funktioniert für neu erstellte UND migrierte Einträge,
  fällt bei alten Obsidian-Mood-Notes (andere Feld-Namen-Schreibweise) sauber auf reinen
  Freitext zurück
- Alle 71 historischen Mood-Notes (22.03.–02.05.2026) migriert via
  `scripts/migrate_mood_notes.py` (dry-run zuerst, dann echter Lauf, dann Stichproben
  gegen die Quell-.md-Dateien verifiziert). Eine Note mit kaputtem Templater-Frontmatter
  (keine echten Werte) wurde übersprungen
- Bugfix während der Umsetzung: journal_entries-Timestamps fehlte die Vienna-Naive-
  Konvertierung (`utc_to_vienna_naive()`), wodurch neue Einträge in der Timeline falsch
  einsortiert wurden (String-Vergleich von UTC- gegen Vienna-Zeitstrings)
