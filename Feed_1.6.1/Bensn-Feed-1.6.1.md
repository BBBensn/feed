---
date_created: 2026-04-11 15:45:25
type: project
status: active
bereich: coding
tags: [project]
date_modified: 2026-04-18 17:10:10
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

### v1.6.1 (2026-04-18)
- Custom Login Modal mit Blur-Overlay (ersetzt Browser-Dialog)
- Guest Login für Shared Feed (konfigurierbares `GUEST_TOKEN`)
- Dynamische Filter-Buttons im Shared Feed (aus tatsächlichen Note-Typen generiert)
- Fits-Farbe: `#ff0051` → `#C9B6BE` (Thistle) — `#ff0051` bleibt für Obsidian Inline-Code
- `[[Obsidian Links]]` in Kategoriefarbe der jeweiligen Note eingefärbt
- Nginx: Auth nur auf `/api/`, HTML-Seiten ohne Nginx-Auth

### v1.6.0 (2026-04-17)
- Shared Feed (`feed.bensn.me/shared`) mit separater HTML-Seite
- `/api/feed/shared` Endpoint (öffentlich, serverseitig gefiltert)
- `share_config.json` — konfigurierbare Kategorien
- `private: true` Frontmatter-Flag schließt einzelne Notes aus
- Lightbox mit Tastatur-Navigation (Pfeiltasten, Escape)

### v1.5.7 (2026-04-17)
- Stabilisierungsrelease — keine Änderungen gegenüber 1.5.6

### v1.5.6 (2026-04-14)
- Telegram-Style Bildgrid (`buildPhotoGrid`):
  - 1 Bild: volle Höhe ohne Beschneiden
  - 2 Bilder: nebeneinander (3:4 Hochformat)
  - 3 Bilder: 1 groß oben (16:9) + 2 unten
  - 4 Bilder: 2×2 Grid
  - 5+ Bilder: erste 4 + `+N` Overlay
- Querformat-Erkennung per `naturalWidth/naturalHeight`
- `object-position: top` — Kopf bleibt, Füße werden bei Kacheln abgeschnitten

### v1.5.5 (2026-04-14)
- HEIC-Support via `pillow-heif`
- Nginx `client_max_body_size 20M`
- `fit`/`fits` Alias-Fix für Filter, Badge und Card-Styling

### v1.5.4 (2026-04-13)
- 2-Spalten Bildgrid (`.note-image-grid`) als Vorstufe zum Telegram-Grid

### v1.5.3 (2026-04-13)
- Bare Upload-URLs direkt als `<img>` gerendert

### v1.5.2 (2026-04-13)
- Upload-Endpoint: beliebiger multipart Feldname + roher Bild-Body als Fallback
- Response als plain text (eine URL pro Zeile) für Shortcuts-Kompatibilität

### v1.5.1 (2026-04-13)
- Kleinfix Upload-Endpoint

### v1.5.0 (2026-04-13)
- Bild-Upload Endpoint (`POST /api/upload`)
- Bildverarbeitung: max 2048px, JPEG 85%, EXIF-Rotation

### v1.4.1 (2026-04-13)
- Sync-Button im Feed-Header
- Port-Fix: Feed-API auf 5002 (Konflikt mit Worktracker auf 5001)

### v1.4.0 (2026-04-13)
- `/api/feed/<note_id>` Einzelnoten-Endpoint
- `/api/sync` manueller Sync-Endpoint

### v1.3.2 (2026-04-13)
- Zeitzonenfix für Tages-Trennlinien (Europe/Vienna statt UTC-Differenz)
- GitHub Webhook in app.py (sofortiger Sync bei Push)

### v1.3.1 (2026-04-13)
- Blockquote-Rendering (`>` Syntax)

### v1.3.0 (2026-04-12)
- `cleanTitle` als Parameter durch `renderMarkdown` durchgereicht (H1-Dedup Fix)

### v1.2.2 (2026-04-12)
- Duplicate H1 / Datum-H1 Stripping verbessert (Regex + Titelvergleich)

### v1.2.1 (2026-04-12)
- Timeline-Parser verbessert
- Fits Card: Akzent-Styling (`#ff0051` Border + Background)

### v1.2.0 (2026-04-12)
- Vollständiges Kategorie-Farbsystem (10 Farben, CSS-Variablen)
- Timeline-Plugin Rendering (` ```timeline ` Blöcke → vertikale Timeline)
- Filter-Bar scrollbar (overflow-x, kein Scrollbar sichtbar)

### v1.1.0 (2026-04-12)
- Markdown-Rendering clientseitig (`renderMarkdown`): Headings, Bold, Italic, HR, Listen, Inline-Code

### v1.0.1 (2026-04-12)
- Tages-Trennlinien (Heute / Gestern / Wochentag + Datum)
- Zeitanzeige pro Eintrag
- Projects Filter-Button

### v1.0.0 (2026-04-12) — Launch
- GitHub Repo + Obsidian Git Plugin Setup
- Server: git clone + Cron für git pull
- Feed-Backend: Flask API `/api/feed`
- Feed-Frontend: chronologischer Feed, bensn.me Design
- Kategorie-Filter (Diary, Mood, Fits), Load-more Pagination
- Git case-sensitivity Fix (`core.ignorecase false`)


## Meilensteine

- [x] GitHub Repo + Obsidian Git Plugin
- [x] Server: git clone + Cron für git pull
- [x] Feed-Backend: Flask API `/api/feed`
- [x] Feed-Frontend: chronologischer Feed, bensn.me Design
- [x] Tages-Trennlinien
- [x] Kategorie-Farbsystem (10 Farben)
- [x] Toggle-Filter (multi-select, kombinierbar, englische Labels)
- [x] Markdown-Rendering clientseitig
- [x] Timeline-Plugin Rendering
- [x] Duplicate H1 / Datum-H1 Stripping
- [x] Git case-sensitivity Fix (`core.ignorecase false`)
- [ ] Kalender-View
- [ ] Kontextdaten-DB (Wetter, Standort)
- [ ] Shortcuts (Fits, Screenshot, Context Log)
- [ ] oEmbed-Rendering (Spotify / YouTube)
- [ ] Worktracker-Daten einbinden
- [ ] Suche
- [ ] PWA (optional)

## Farb-Konzept

| Type                 | Farbe         | Hex       |     
| -------------------- | ------------- | --------- |  
| Alle / UI-Akzent     | Fresh Sky     | `#00a6ed` |          
| Obsidian Inline-Code | Hot Fuchsia   | `#ff0051` |          
| Diary                | Sandy Clay    | `#e5b181` |          
| Mood                 | Celadon       | `#b8ebd0` |          
| Fits                 | Thistle       | `#C9B6BE` |          
| Reflexion            | Amber Flame   | `#ffb400` |          
| Symptome             | Vibrant Coral | `#f96f5d` |          
| Therapie             | Burnt Rose    | `#9c3848` |          
| Projekt              | Dusk Blue     | `#1d4e89` |          
| Ideas                | Royal Violet  | `#6622cc` |          
| Arbeit               | Pine Teal     | `#065143` |          


![[Bensn-Feed-1775958583196.webp]]
![[Bensn Landing-1775870767414.webp]]
![[Bensn-Feed-1776509816368.webp]]
## Notizen

Verwandt: [[Bensn-Hub]] · [[Worktracker]]