# Bensn-Feed — CLAUDE.md

Projekt-spezifischer Kontext. Ergänzt `~/.claude/CLAUDE.md`.
Ablageort: `~/Documents/Coding/bensn-hub/feed/CLAUDE.md`

---

## Projekt-Basics

- **Name:** Bensn-Feed
- **Domain:** feed.bensn.me
- **Version:** v2.0.2 (Frontend) / app.py-Stand aus v1.7.7 (Backend)
- **Status:** active — wird gerade grundlegend umgebaut (siehe Roadmap: Obsidian-Ablösung)
- **Stack:** Vanilla JS + Flask (Python), bensn.me Design System (`/shared/bensn.css`+`bensn.js`)

---

## Was ist das Projekt?

Persönlicher scrollbarer Feed auf `feed.bensn.me`. Zeigt aktuell alle Obsidian Journal-Notes
aus `01_Journal` (per Git-Sync gespiegelt) gemischt mit Worktracker-Events (Schichten/Pausen,
live von der hub-api abgefragt). Aktuell noch kein eigenes Eingabe-Interface — das ändert sich
im laufenden Umbau (siehe Roadmap).

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
| `GET /api/feed/combined` | Cookie (bensn-auth) | Notes + Worktracker-Events |
| `GET /api/feed/combined/shared` | öffentlich | Shared Notes + Worktracker (ohne Details) |
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
| UI-Akzent | Fresh Sky | `#00a6ed` | — |

Sharing-Filterung: `share_config.json` auf Server + `private: true` im Note-Frontmatter.

---

## Git

- **Repo:** `git@github.com:BBBensn/feed.git`

---

## Projekt-spezifische Konventionen

- Backend (`app.py`) liest den Vault direkt von Disk — kein DB-Cache (ändert sich mit dem Umbau,
  sobald `journal_entries` in Postgres existiert)
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
| — | Health → Feed Integration (Medikamente/BP/Mahlzeiten als Timeline-Events) | ⬜ geplant |
| — | `journal_entries`-Schema + natives Mood-Compose + Mood-Migration | ⬜ geplant |
| — | Compose-UI für restliche 8 Journal-Typen | ⬜ geplant |
| — | Vollständige Historien-Migration + Obsidian-Decommission | ⬜ geplant |

Details zur vollständigen Versionshistorie: `docs/changelogs/CHANGELOG.md`.

---

## Obsidian-Doku

- Projekt-MD: `03_Projects/Coding PC/Bensn-Hub/Feed/Feed.md`
- Changelogs: `03_Projects/Coding PC/Bensn-Hub/Feed/Changelogs/`
