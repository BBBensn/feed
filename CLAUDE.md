# Bensn-Feed — CLAUDE.md

Projekt-spezifischer Kontext. Ergänzt `~/.claude/CLAUDE.md`.
Ablageort: `~/Documents/Coding/bensn-hub/feed/CLAUDE.md`

---

## Projekt-Basics

- **Name:** Bensn-Feed
- **Domain:** feed.bensn.me
- **Version:** v2.1.0 (natives Mood-Compose + journal_entries)
- **Status:** active — Obsidian-Ablösung läuft (Mood erledigt, 8 weitere Typen + volle
  Historien-Migration folgen, siehe Roadmap)
- **Stack:** Vanilla JS + Flask (Python), bensn.me Design System (`/shared/bensn.css`+`bensn.js`)

---

## Was ist das Projekt?

Persönlicher scrollbarer Feed auf `feed.bensn.me`. Zeigt Obsidian Journal-Notes aus
`01_Journal` (per Git-Sync gespiegelt, für 8 von 9 Typen noch die einzige Quelle),
native `journal_entries` aus Postgres (aktuell nur `mood`, siehe unten), Worktracker-Events
und Health-Events (Medikamente/Blutdruck/Mahlzeiten) gemischt in einer Timeline.

**Mood-Einträge werden seit v2.1.0 nativ im Feed erstellt** — ein "+"-Button öffnet ein
Apple-Journal-artiges Check-in (Valenz-Slider -100..100, Zusammenhang-/Beschreibung-
Multiselect mit den echten Tag-Listen aus der alten ModalForms-Config, Tagesreflexion-
Toggle), kein Obsidian mehr nötig dafür. Alle 71 historischen Mood-Notes (22.03.–02.05.2026)
wurden per `scripts/migrate_mood_notes.py` migriert (`migrated_from: obsidian` bzw.
`apple_journal` für die ~ursprünglich aus Apple Journal importierten). Eine Note
(`2026-05-06-1344-mood.md`) hatte kaputtes Frontmatter (nicht ausgeführtes Templater-Syntax
statt echter Werte, vermutlich ein Templater-Fehler beim Erstellen) und wurde übersprungen —
sie enthält ohnehin keine echten Mood-Daten.

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
│   └── migrate_mood_notes.py   ← einmaliges Migrationsskript (siehe Kommentar im File)
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
| `GET /api/feed` | Cookie (bensn-auth) | Alle Notes (privat) |
| `GET /api/feed/shared` | öffentlich | Gefilterte Notes per share_config.json |
| `GET /api/feed/combined` | Cookie (bensn-auth) | Notes + `journal_entries` + Worktracker + Health-Events |
| `GET /api/feed/combined/shared` | öffentlich | Shared Notes + `journal_entries` (gefiltert) + Worktracker (ohne Details, KEINE Health-Events) |
| `GET/POST /api/journal/entries`, `/entry` | Cookie (bensn-auth) | Native Journal-Einträge CRUD (aktuell nur `mood` im Compose-UI genutzt) |
| `PATCH/DELETE /api/journal/entry/<id>` | Cookie (bensn-auth) | Editieren / soft-löschen |
| `GET /api/journal/mood-summary` | Cookie (bensn-auth) | Valenz-Verlauf für Dashboards |
| `GET /api/feed/stats` | Cookie (bensn-auth) | Statistiken nach Typ/Folder |
| `GET /api/feed/<note_id>` | Cookie (bensn-auth) | Einzelne Note |
| `GET/POST /api/share/config` | Cookie / `X-API-Key` (POST) | Sharing-Config lesen/schreiben |
| `POST /api/upload` | öffentlich (nginx, kein Cookie) | Bild-Upload (HEIC/JPEG, max 20MB) — für iOS Shortcuts |
| `GET /api/oembed` | öffentlich | Spotify/YouTube oEmbed Proxy |
| `POST /api/webhook` | HMAC SHA-256 | GitHub Webhook → git sync |
| `POST /api/sync` | Cookie (bensn-auth) | Manueller git sync |
| `GET /health` | öffentlich | Health Check |

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

## Obsidian Vault Sync (wird im laufenden Umbau abgeschafft)

```
iPhone/Mac (Obsidian Git Plugin, auto-commit ~10min)
  → push → BBBensn/BensnKnowledge (privat)
  → GitHub Webhook → POST /api/webhook (sofort)
  → Cron alle 10min: git fetch --all && reset --hard origin/main
     GIT_SSH_COMMAND='ssh -i /root/.ssh/feed_deploy'

Vault auf Server: /var/www/feed/vault/
Journal-Pfad:    /var/www/feed/vault/01_Journal/
```

**Wird abgelöst:** siehe Roadmap — Journal-Einträge wandern nach `journal_entries` (Postgres),
natives Compose-UI im Feed ersetzt Obsidian als Eingabe-Tool, danach wird dieser
Sync-Mechanismus komplett entfernt.

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
| — | Compose-UI für restliche 8 Journal-Typen | ⬜ geplant |
| — | Vollständige Historien-Migration + Obsidian-Decommission | ⬜ geplant |

Details zur vollständigen Versionshistorie: `docs/changelogs/CHANGELOG.md`.

---

## Obsidian-Doku

- Projekt-MD: `03_Projects/Coding PC/Bensn-Hub/Feed/Feed.md`
- Changelogs: `03_Projects/Coding PC/Bensn-Hub/Feed/Changelogs/`
