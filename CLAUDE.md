# Bensn-Feed — CLAUDE.md

Projekt-spezifischer Kontext. Ergänzt `~/.claude/CLAUDE.md`.
Ablageort: `~/Documents/Coding/bensn-hub/feed/CLAUDE.md`

---

## Projekt-Basics

- **Name:** Bensn-Feed
- **Domain:** feed.bensn.me
- **Version:** v2.4.0 (Edit/Delete, Tags-Anzeige, editierbarer Zeitpunkt, Limit-Fix)
- **Status:** active — Obsidian-Ablösung vollständig abgeschlossen (Compose-UI für alle 9
  Typen, komplette Historie migriert, Git-Sync abgeschaltet)
- **Stack:** Vanilla JS + Flask (Python) + PostgreSQL, bensn.me Design System (`/shared/bensn.css`+`bensn.js`)

---

## Was ist das Projekt?

Persönlicher scrollbarer Feed auf `feed.bensn.me`. Zeigt **ausschließlich** `journal_entries`
aus Postgres (alle 9 Typen, komplette Historie seit 2026-03 bzw. dem jeweils ersten Eintrag
pro Typ), gemischt mit Worktracker-Events und Health-Events (Medikamente/Blutdruck/
Mahlzeiten) in einer Timeline. Obsidian ist komplett aus dem Bild — weder als Lese- noch als
Schreibquelle (siehe "Obsidian Vault Sync" unten für die Abschalt-Details).

**Alle 9 Journal-Typen haben ein natives Compose-UI** — ein "+"-Button öffnet einen
Typ-Picker, dann entweder das Mood-Check-in (Valenz-Slider, Zusammenhang-/Beschreibung-
Multiselect mit den echten Tag-Listen aus der ehemaligen ModalForms-Config,
Tagesreflexion-Toggle) oder ein generisches Formular (Titel, Tags, Body-Textarea — bei den
strukturierten Typen mit vorausgefüllten Markdown-Überschriften als Vorlage, z.B. `## Was /
Kontext / Verlauf / Maßnahmen` für Symptome — plus 0-2 typ-spezifische Zusatzfelder, siehe
`ENTRY_TYPE_CONFIG` im Frontend). `fits` erlaubt zusätzlich Bild-Upload über den bestehenden
`/api/upload`-Endpoint.

Alle 71 historischen Mood-Notes (22.03.–02.05.2026) wurden bereits per
`scripts/migrate_mood_notes.py` migriert (`migrated_from: obsidian` bzw. `apple_journal`
für die ursprünglich aus Apple Journal importierten). Eine Note (`2026-05-06-1344-mood.md`)
hatte kaputtes Frontmatter (nicht ausgeführtes Templater-Syntax statt echter Werte) und
wurde übersprungen — sie enthält ohnehin keine echten Mood-Daten.

Öffentlicher Teilbereich: `feed.bensn.me/shared` — gefiltert per `share_config.json` +
`private: true` im Note-Frontmatter.

---

## Lokale Struktur

```
~/Documents/Coding/bensn-hub/feed/
├── index.html          ← Hauptfeed (aktuell)
├── s.html              ← Shared/öffentlicher Feed (deployed als shared.html)
├── manifest.json
├── sw.js
├── share_config.json
├── api/
│   ├── app.py           ← Flask Backend
│   └── requirements.txt
├── schema.sql            ← journal_entries (per pg_dump/CREATE TABLE, kein Migrationsrunner)
├── scripts/
│   ├── migrate_mood_notes.py     ← einmaliges Migrationsskript für Mood (bereits gelaufen)
│   └── migrate_journal_notes.py  ← einmaliges Migrationsskript für die restlichen 8 Typen (bereits gelaufen)
├── Desing/              ← frühe Design-Mockups/Prototypen (Referenz, kein Live-Code)
├── docs/changelogs/
└── CLAUDE.md
```

---

## Remote-Struktur

```
/var/www/feed/
├── api/
│   └── app.py          ← Flask Backend (feed-api.service, Port 5002)
├── vault/              ← git clone BBBensn/BensnKnowledge (read-only, wird in Phase 5 des Umbaus entfernt)
├── share_config.json
└── public/
    ├── index.html
    ├── shared.html      ← lokal: s.html
    ├── sw.js
    ├── manifest.json
    └── uploads/
```

Static Shared Assets (Design System): `/var/www/shared/bensn.css` + `/var/www/shared/bensn.js`

---

## Services & Ports

| Dienst | Port | systemd-Service |
|--------|------|-----------------|
| Feed API (Flask) | 5002 | `feed-api.service` |
| hub-api (Docker) | 5001 | `bensn-api` |

Feed-API fragt Worktracker-Daten intern via `http://localhost:5001` ab (`fetch_shift_events()`).

---

## Deploy

```bash
scp ~/Documents/Coding/bensn-hub/feed/index.html bensn:/var/www/feed/public/index.html
scp ~/Documents/Coding/bensn-hub/feed/s.html bensn:/var/www/feed/public/shared.html
scp ~/Documents/Coding/bensn-hub/feed/manifest.json bensn:/var/www/feed/public/manifest.json
scp ~/Documents/Coding/bensn-hub/feed/sw.js bensn:/var/www/feed/public/sw.js
scp ~/Documents/Coding/bensn-hub/feed/api/app.py bensn:/var/www/feed/api/app.py
ssh bensn systemctl restart feed-api
```

---

## API Routes (feed-api, Port 5002)

| Route | Auth | Beschreibung |
|-------|------|--------------|
| `GET /api/feed/combined` | Cookie (bensn-auth) | `journal_entries` + Worktracker + Health-Events |
| `GET /api/feed/combined/shared` | öffentlich | Shared `journal_entries` (gefiltert) + Worktracker (ohne Details, KEINE Health-Events) |
| `GET/POST /api/journal/entries`, `/entry` | Cookie (bensn-auth) | Journal-Einträge CRUD (alle 9 Typen) |
| `PATCH/DELETE /api/journal/entry/<id>` | Cookie (bensn-auth) | Editieren / soft-löschen |
| `GET /api/journal/mood-summary` | Cookie (bensn-auth) | Valenz-Verlauf für Dashboards |
| `GET/POST /api/share/config` | Cookie / `X-API-Key` (POST) | Sharing-Config lesen/schreiben |
| `POST /api/upload` | öffentlich (nginx, kein Cookie) | Bild-Upload (HEIC/JPEG, max 20MB) — für iOS Shortcuts + Fits-Compose |
| `GET /api/oembed` | öffentlich | Spotify/YouTube oEmbed Proxy |
| `GET /health` | öffentlich | Health Check |

**Entfernt (2026-09-16, Obsidian-Decommission):** `/api/feed`, `/api/feed/shared`,
`/api/feed/stats`, `/api/feed/<note_id>`, `/api/webhook`, `/api/sync`, `/api/wikilinks` —
alle hingen am Datei-Lesepfad, keine wurde vom aktuellen Frontend genutzt.

---

## Auth

Zentrales Cookie-System (`bensn-auth`, Port 5003) via nginx `auth_request` — siehe
`bensn-meta/auth/bensn-auth-v2/nginx-feed.bensn.me` für die exakte Config. Bewusste
Ausnahmen ohne Cookie-Auth: `/api/upload` (iOS Shortcuts), `/api/feed/shared`,
`/api/feed/combined/shared`, `/api/oembed`, `/api/webhook`, `/shared`, `/uploads/`.

*(Hinweis: eine ältere Version dieser Datei nannte fälschlich Nginx Basic Auth als aktuellen
Mechanismus — das war ein Zwischenstand vor der Migration auf bensn-auth in v1.7.x und ist
mittlerweile korrigiert.)*

---

## Obsidian Vault Sync — abgeschaltet seit 2026-09-16

Bis v2.2.0 lief hier ein Git-Sync (iPhone/Mac Obsidian Git-Plugin → GitHub-Webhook +
10-Minuten-Cron → `/var/www/feed/vault/` → `load_all_notes()` liest `.md`-Dateien direkt
von Disk). Das ist komplett entfernt:

- Cron-Eintrag (`*/10 * * * * ... feed/vault ...`) aus der Root-Crontab gelöscht (Backup:
  `/tmp/crontab.bak` auf dem Server, falls doch mal gebraucht)
- `/var/www/feed/vault/` (288MB Git-Clone) gelöscht — reine Mirror-Kopie, die echte Quelle
  bleibt der lokale Obsidian-Vault + das private `BensnKnowledge`-GitHub-Repo, beide
  unangetastet
- `/api/webhook`, `/api/sync`, `/api/feed`, `/api/feed/shared`, `/api/feed/stats`,
  `/api/feed/<note_id>`, `/api/wikilinks` aus `app.py` entfernt (alle hingen an
  `load_all_notes()`/`VAULT_PATH`, keiner wurde vom aktuellen Frontend genutzt)
- `load_all_notes()`, `load_note()`, `extract_images()`, `extract_media_links()`,
  `parse_date()`, `date_from_filename()` als tote Funktionen entfernt
- nginx-Config bereinigt (`bensn-meta/nginx/feed.bensn.me`): Location-Blöcke für die
  entfernten Routen raus
- **Nicht entfernt:** der GitHub-Webhook auf dem `BensnKnowledge`-Repo selbst (Settings →
  Webhooks) feuert technisch weiterhin bei jedem Push, bekommt jetzt aber nur noch ein
  harmloses 302/404 zurück — kann bei Gelegenheit manuell in GitHub gelöscht werden, ist
  aber kein Fehlerzustand

Der Feed liest jetzt ausschließlich aus `journal_entries` (Postgres) — Schreiben in
Obsidian hat ab sofort keine Wirkung mehr auf den Feed.

---

## Note-Typen & Farben

| Type | Farbe | Hex | Shared? |
|------|-------|-----|---------|
| diary | Sandy Clay | `#e5b181` | ✅ |
| mood | Celadon | `#b8ebd0` | ✅ |
| reflexion / reflexionen | Amber Flame | `#ffb400` | ✅ |
| symptome / symptom | Vibrant Coral | `#f96f5d` | ❌ (per aktueller share_config.json) |
| therapie | Burnt Rose | `#9c3848` | ✅ |
| fits / fit | Thistle | `#C9B6BE` | ❌ |
| arbeit | Pine Teal | `#065143` | ❌ |
| idea / ideas | Royal Violet | `#6622cc` | ❌ |
| project_log | Dusk Blue | `#1d4e89` | ❌ |
| medication_taken / bp_reading / meal_logged | Teal | `#22d3d3` | ❌ (nie geshared, siehe unten) |
| UI-Akzent | Fresh Sky | `#00a6ed` | — |

Sharing-Filterung: `share_config.json` auf Server + `private: true` im Note-Frontmatter.
Health-Events sind eine Ausnahme davon — die werden in `feed_combined_shared()` und
`share_feed()` (dem `/api/share/<token>`-Endpoint) bewusst nie eingemischt, unabhängig von
`share_config.json`. Medizinische Daten haben auf einem Link, den man mit anderen teilt,
nichts verloren.

---

## Health-Integration (`health.bensn.me`)

Seit v2.0.3 (2026-09-16): `fetch_medication_events()`, `fetch_bp_events()`,
`fetch_meal_events()` in `api/app.py` lesen `health_medication_logs`/`health_bp_logs`/
`health_meals` **direkt aus Postgres** (nicht per internem HTTP-Call wie beim Worktracker) —
feed-api hat über die geteilte DB-Verbindung fürs Sharing-Feature ohnehin schon Zugriff,
ein zweites HTTP-Client-Pattern wäre unnötig gewesen. Nur in `feed_combined()` gemergt
(privat), nicht in den beiden Shared-Varianten.

---

## Git

- **Repo:** `git@github.com:BBBensn/feed.git`

---

## Projekt-spezifische Konventionen

- Backend (`app.py`) liest den Vault direkt von Disk für die 8 noch-nicht-migrierten Typen —
  `journal_entries` in Postgres ist die Quelle für `mood`, sobald ein Typ vollständig auf
  natives Compose umgestellt ist, sollte sein Obsidian-Lesepfad entfallen (siehe Roadmap)
- `journal_row_to_note()` mappt DB-Zeilen auf exakt dasselbe Shape wie `load_note()`
  (type/title/content/date/tags/meta) — der Feed-Renderer behandelt beide Quellen identisch,
  ohne das zu wissen
- `git pull --ff-only` funktioniert auf dem Server nicht → immer `fetch --all && reset --hard origin/main`
- Service Worker Cache: `sw.js`-Cache-Version bumpen bei PWA-Updates

---

## Roadmap

| Version | Feature | Status |
|---------|---------|--------|
| v1.0.0–v1.5.x | Initialer Launch: Vault-Sync, Notes+Worktracker-Feed | ✅ deployed |
| v1.6.0–v1.6.4 | Frontend-Iterationen | ✅ deployed |
| v1.7.0–v1.7.9 | Sharing-System, Migration auf bensn-auth Cookie | ✅ deployed |
| v2.0.0–v2.0.2 | Login-Overlay entfernt, Wikilink-Stats-Drawer | ✅ deployed |
| v2.0.3 | Health → Feed Integration (Medikamente/BP/Mahlzeiten als Timeline-Events) | ✅ deployed (2026-09-16) |
| v2.1.0 | `journal_entries`-Schema + natives Mood-Compose + Mood-Migration (71 Notes) | ✅ deployed (2026-09-16) |
| v2.2.0 | Compose-UI für restliche 8 Journal-Typen (Typ-Picker, generisches Formular, Body-Templates, Bild-Upload für Fits) | ✅ deployed (2026-09-16) |
| v2.3.0 | Vollständige Historien-Migration (294 weitere Einträge, 8 Typen) + Obsidian-Decommission (Cron, Webhook, Vault-Clone, tote Routen/Tabellen entfernt) | ✅ deployed (2026-09-16) |
| v2.4.0 | Bugfix: `limit=500` schnitt bei kombiniertem Pool (Journal+Worktracker+Health) Einträge vor dem 10. Mai ab (auf 5000 angehoben); Bugfix: Tags wurden gespeichert, aber nie angezeigt; Sync-Button entfernt (war für Git-Sync, tot seit v2.3.0); Edit-Zeitpunkt + Löschen für alle Journal-Einträge; Zeitpunkt-Feld (Standard jetzt, editierbar) in Mood- und generischem Compose-Sheet | ✅ deployed (2026-09-16) |

Details zur vollständigen Versionshistorie: `docs/changelogs/CHANGELOG.md`.

---

## Obsidian-Doku

- Projekt-MD: `03_Projects/Coding PC/Bensn-Hub/Feed/Feed.md`
- Changelogs: `03_Projects/Coding PC/Bensn-Hub/Feed/Changelogs/`
