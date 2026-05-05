---
date_created: 2026-04-11 15:45:25
type: project
status: active
bereich: coding
tags: [project]
date_modified: 2026-04-18 14:00:00
---

# Bensn-Feed

## Was ist das Projekt?

Persönlicher Feed auf `feed.bensn.me`. Vorbild: Apple Journal / early Facebook. Passive Darstellungsschicht für alle Obsidian Journal-Notes aus `01_Journal`, ergänzt durch automatisch gesammelte Kontextdaten (Wetter, Standort, Worktracker). Kein eigenes Eingabe-Interface — Obsidian bleibt das Schreibwerkzeug.

## Ziel / Done-Definition

- Obsidian-Notes werden ausgelesen und als scrollbarer Feed dargestellt
- Kalenderansicht als Alternative zum Feed
- Kontextdaten (Wetter, Standort) werden per Timestamp mit Notes verknüpft und angezeigt
- Spotify/YouTube-Links in Notes werden automatisch als Player/Preview gerendert (oEmbed)
- Filter- und Suchfunktion über alle Einträge

## Scope

**Drin:**

- Lesen und Darstellen aller Notes aus `01_Journal` (Diary, Mood, Fits, Reflexionen, Symptome, Therapie, Arbeit, ProjectLogs, Ideas)
- Fotos: Upload via Apple Shortcut → `/api/upload` → JPEG komprimiert gespeichert unter `/uploads/`, HEIC-Support via pillow-heif
- Telegram-Style Bildgrid (1–5 Bilder, Hochformat, Querformat-Erkennung, +N Overlay, Lightbox)
- Geteilter Feed unter `feed.bensn.me/shared` — konfigurierbar welche Kategorien geteilt werden
- `private: true` Frontmatter-Flag um einzelne Notes vom Shared Feed auszuschließen
- Custom Login Modal (Hauptfeed: Basic Auth via JS; Shared: Token-basiert)
- Verknüpfung mit Kontextdaten aus DB über Timestamp (Wetter, Standort) — geplant
- oEmbed-Rendering für Spotify, YouTube — geplant
- Kalender-View — geplant
- Worktracker-Daten einbinden — geplant

**Nicht drin:**

- Eigenes Eingabe-Interface für Notes (das bleibt Obsidian / Shortcuts)
- Verwaltung oder Bearbeitung von Notes
- Eigene Nutzerverwaltung / Accounts
- Inhalte aus anderen Vault-Ordnern (02_Notes, 03_Projects, etc.)

## Architektur

### Datenprinzip

```
Obsidian / BensnKnowledge (Schreiben — einzige Wahrheitsquelle)
└── 01_Journal/
    ├── Diary/
    ├── Mood/
    ├── Fits/
    ├── Reflexionen/
    ├── Symptome/
    ├── Therapie/
    ├── Arbeit/
    ├── Projects/
    └── Ideas/

        ↓ Obsidian Git Plugin (auto-commit, alle ~10 min)
          + GitHub Webhook (sofort bei Push)

GitHub Repo: BensnKnowledge (privat, BBBensn/BensnKnowledge)

        ↓ Server: git fetch + reset --hard (Cron + Webhook)

/var/www/feed/vault/01_Journal/   ← read-only Kopie

        ↓

Feed-Backend (Flask / Python, Port 5002, systemd feed-api)
├── liest alle .md rekursiv
├── parsed Frontmatter (date_created, type, tags, private, …)
├── GET /api/feed → JSON (geschützt via Nginx Basic Auth)
├── GET /api/feed/shared → JSON (öffentlich, gefiltert per share_config.json)
└── POST /api/upload → Bild-Upload, HEIC-Support

feed.bensn.me (Frontend)
├── index.html — Hauptfeed (Login-geschützt)
└── shared.html — Geteilter Feed (Guest-Passwort)
```

### Sharing-System

`/var/www/feed/share_config.json` definiert welche Note-Typen standardmäßig geteilt werden:

```json
{
  "shared_types": ["diary", "mood", "reflexion", "reflexionen", "therapie", "symptome", "symptom"],
  "blocked_types": ["fit", "fits", "arbeit", "idea", "ideas", "project_log", "projectlog", "wortwurzel"]
}
```

Einzelne Notes können mit `private: true` im Frontmatter vom Shared Feed ausgeschlossen werden.

### Login

- **Hauptfeed** (`feed.bensn.me`): Nginx Basic Auth, bedient durch custom JS-Modal (Credentials in sessionStorage)
- **Shared Feed** (`feed.bensn.me/shared`): Token-basiert, Passwort in localStorage, Token in `shared.html` konfigurierbar (`GUEST_TOKEN`)

### Markdown-Rendering (clientseitig)

- Headings, Bold, Italic, HR, Listen, Inline-Code, Blockquotes
- `[[Obsidian Links]]` → farbig in Kategoriefarbe der jeweiligen Note
- ` ```timeline ` Blöcke → vertikale Timeline-Komponente
- Duplicate H1 / Datum-H1 werden automatisch entfernt
- Bild-Zeilen (`![]()`) werden aus dem Textbody herausgefiltert und separat als Grid gerendert

## Stack

| Komponente | Tech |
|---|---|
| Sync | Obsidian Git Plugin → GitHub → `git fetch + reset` per Cron + Webhook |
| Backend | Python / Flask, systemd `feed-api`, Port 5002 |
| Bild-Upload | `/api/upload`, pillow-heif (HEIC), max 2048px JPEG |
| Frontend | Vanilla JS, bensn.me Design System |
| Hosting | `feed.bensn.me` via Nginx + Let's Encrypt |
| Auth | Nginx Basic Auth + JS-Modal (Hauptfeed), Token (Shared) |

## Deploy-Pfade

```
/var/www/feed/vault/         ← git clone BensnKnowledge (read-only)
/var/www/feed/api/app.py     ← Flask Backend
/var/www/feed/public/        ← Frontend
  ├── index.html             ← Hauptfeed
  ├── shared.html            ← Geteilter Feed
  └── uploads/               ← Hochgeladene Bilder
/var/www/feed/share_config.json  ← Sharing-Konfiguration
```

## Changelog

### v1.6.1 (2026-04-18) — in Arbeit
- Custom Login Modal (Blur-Overlay, bensn.me Design)
- Guest Login für Shared Feed (konfigurierbares Passwort)
- Fits-Farbe: `#ff0051` → `#C9B6BE` (Thistle)
- `[[Obsidian Links]]` in Kategoriefarbe der jeweiligen Note

### v1.6.0 (2026-04-18)
- Shared Feed (`feed.bensn.me/shared`) mit `share_config.json`
- `private: true` Frontmatter-Flag
- Nginx Basic Auth Login
- Bilder: `object-position: top` (Kopf bleibt, Füße werden abgeschnitten)
- Lightbox mit Tastatur-Navigation

### v1.5.0 (2026-04-14)
- Telegram-Style Bildgrid (1–5 Bilder, Hochformat/Querformat-Erkennung, +N Overlay)
- 1-Bild: volle Höhe ohne Beschneiden
- `fit`/`fits` Alias-Fix für Filter + Badge + Card
- HEIC-Support via pillow-heif
- Nginx `client_max_body_size 20M`

### v1.4.0 (2026-04-13)
- Bild-Upload Endpoint (`/api/upload`)
- Apple Shortcut für Foto-Upload
- `![](url)` Markdown direkt in Feed gerendert
- Port-Fix: Feed-API auf 5002 (war Konflikt mit Worktracker auf 5001)

### v1.3.0 (2026-04-12)
- GitHub Webhook für sofortigen Sync bei Push
- Blockquote-Rendering
- Timeline-Plugin Rendering (` ```timeline `)
- Sync-Button im Feed

### v1.0.0 (2026-04-12) — Launch
- GitHub Repo + Obsidian Git Plugin
- Server: git clone + Cron für git pull
- Feed-Backend: Flask API `/api/feed`
- Feed-Frontend: chronologischer Feed, bensn.me Design
- Tages-Trennlinien, Kategorie-Farbsystem, Toggle-Filter
- Markdown-Rendering clientseitig
- Duplicate H1 / Datum-H1 Stripping
- Git case-sensitivity Fix

## Offene Meilensteine

- [ ] Kalender-View
- [ ] Kontextdaten-DB (Wetter, Standort via Shortcut → API)
- [ ] oEmbed-Rendering (Spotify / YouTube)
- [ ] Worktracker-Daten einbinden (Schichten im Feed)
- [ ] Suche
- [ ] PWA (offline-fähig, Add to Home Screen)

## Farb-Konzept

| Type | Farbe | Hex |
|---|---|---|
| Alle / UI-Akzent | Fresh Sky | `#00a6ed` |
| Obsidian Inline-Code | Hot Fuchsia | `#ff0051` |
| Diary | Sandy Clay | `#e5b181` |
| Mood | Celadon | `#b8ebd0` |
| Fits | Thistle | `#C9B6BE` |
| Reflexion | Amber Flame | `#ffb400` |
| Symptome | Vibrant Coral | `#f96f5d` |
| Therapie | Burnt Rose | `#9c3848` |
| Projekt | Dusk Blue | `#1d4e89` |
| Ideas | Royal Violet | `#6622cc` |
| Arbeit | Pine Teal | `#065143` |

## Notizen

Verwandt: [[Bensn-Hub]] · [[Worktracker]]
