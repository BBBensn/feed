---
date_created: 2026-09-16 03:11:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-16 03:11:00
---

# v2.3.0 — Vollständige Historien-Migration + Obsidian-Decommission (2026-09-16)
- Alle historischen Journal-Notes der restlichen 8 Typen migriert via
  `scripts/migrate_journal_notes.py` (dry-run gegen echte Feld-Stichproben verifiziert,
  dann echter Lauf): diary 213, project_log 33, fits 21, ideas 12, therapie 6, arbeit 4,
  symptome 3, reflexion 2 — macht zusammen mit den 71 Mood-Notes 365 migrierte Einträge
  insgesamt. Eine Reflexion ohne `type:`-Feld wurde per Ordner-Fallback korrekt als
  `reflexion` erkannt; Bilder (Fits) wurden aus dem Markdown-Body extrahiert und ins
  `images`-Array übernommen
- Bugfix während der Umsetzung: `journal_row_to_note()` gab `images` als reine URL-Strings
  zurück, das Frontend erwartet aber `{alt, url}`-Objekte (`buildPhotoGrid()` liest
  `img.url`) — ohne den Fix wären Fits-Fotos für migrierte/native Einträge nicht angezeigt
  worden
- Obsidian als Lesequelle für den Feed komplett abgeschaltet:
  - Cron-Sync (`*/10 * * * * ... feed/vault ...`) aus der Root-Crontab entfernt
  - `/var/www/feed/vault/` (288MB Git-Mirror) gelöscht
  - `/api/webhook`, `/api/sync`, `/api/feed`, `/api/feed/shared`, `/api/feed/stats`,
    `/api/feed/<note_id>`, `/api/wikilinks` aus `app.py` entfernt (alle unbenutzt, alle
    abhängig vom jetzt entfernten Datei-Lesepfad)
  - `load_all_notes()`, `load_note()`, `extract_images()`, `extract_media_links()`,
    `parse_date()`, `date_from_filename()` als tote Funktionen entfernt
  - `/api/feed/combined` + beide Shared-Varianten lesen jetzt ausschließlich aus
    `fetch_journal_events()` (Postgres) statt `load_all_notes() + fetch_journal_events()`
  - nginx-Config bereinigt (tote Location-Blöcke für die entfernten Routen)
  - Tote Tabellen `obsidian_entries`, `feed_items` und das schon in Phase 1 als tot
    markierte `health_logs` gedroppt
- Nicht angefasst: der GitHub-Webhook auf dem `BensnKnowledge`-Repo selbst feuert
  technisch weiter (bekommt jetzt ein harmloses 302/404), kann bei Gelegenheit manuell in
  den GitHub-Repo-Settings gelöscht werden
