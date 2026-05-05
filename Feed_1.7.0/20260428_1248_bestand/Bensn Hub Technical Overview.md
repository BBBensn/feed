---
date_created: 2026-04-19 20:05:59
type: note
tags:
  - project
date_modified: 2026-04-28 12:22:18
---

# [[Bensn-Hub]] Technical Reference

> Letzte Aktualisierung: 2026-04-19 Zweck: Vollständiger technischer Überblick für neue Chat-Sessions

---

## Server

|Eigenschaft|Wert|
|---|---|
|Provider|Hetzner CX23, Nürnberg|
|IP|`178.104.133.228`|
|OS|Ubuntu 24.04|
|Disk|37 GB|
|RAM|~41% belegt|
|SSH|`root@178.104.133.228`|

---

## Port-Belegung (vollständig)

|Port|Prozess|Service|Erreichbar von|
|---|---|---|---|
|80|nginx|HTTP → HTTPS Redirect|public|
|443|nginx|HTTPS Reverse Proxy|public|
|5001|docker-proxy → `bensn-api`|Worktracker + bensn-OS API|localhost only|
|5002|python3 (systemd)|Feed API (`feed-api.service`)|localhost only|
|5003|python3 (systemd)|Auth Service (`bensn-auth.service`)|localhost only|
|5000|docker-proxy → `weather-api`|Weather Location API|public|
|3000|docker-proxy → `weather-grafana`|Grafana|public|
|5432|docker-proxy → `bensn-postgres`|PostgreSQL|localhost only|
|8081|docker-proxy → `stirling-pdf`|Stirling PDF|public|
|8086|docker-proxy → `weather-influxdb`|InfluxDB|public|

**Nächster freier Port für neuen Service: 5004**

---

## Nginx Vhosts (`/etc/nginx/sites-enabled/`)

|Datei|Domain|Backend|Auth|
|---|---|---|---|
|`bensn.me`|`bensn.me`|Static `/var/www/bensn.me`|offen|
|`auth.bensn.me`|`auth.bensn.me`|Proxy → 5003 (bensn-auth)|—|
|`worktracker.bensn.me`|`worktracker.bensn.me`|Static `/var/www/worktracker`, `/api/*` → 5001|🔒 Cookie (außer `/api/*`)|
|`feed.bensn.me`|`feed.bensn.me`|Proxy → 5002, Static `/var/www/feed/public`|🔒 Cookie (außer `/shared`, `/api/upload`)|
|`tracking.bensn.me`|`tracking.bensn.me`|Static `/var/www/tracking`, `/api/*` → 5001|🔒 Cookie|
|`location.bensn.me`|`location.bensn.me`|Static `/var/www/location`, `/api/*` → 5001|🔒 Cookie (außer `/api/location`)|
|`data.bensn.me`|`data.bensn.me`|Proxy → 3000 (Grafana)|🔒 Grafana-eigen|
|`pdf.bensn.me`|`pdf.bensn.me`|Proxy → 8081 (Stirling PDF)|🔒 Stirling-eigen|

### worktracker.bensn.me Auth-Logik

- `/api/*` → Proxy zu 5001, `X-API-Key` wird von **Nginx injiziert** (nicht vom Frontend gesendet)
    
- CORS OPTIONS requests werden direkt von Nginx beantwortet (204)
    
- `/shared/` → alias `/var/www/shared/`
    
- `/` → Static `/var/www/worktracker`
    
- `/api/feed/shared`, `/api/feed/combined/shared`, `/api/oembed` → kein Auth (öffentlich)
    
- `/api/*` → Nginx Basic Auth (`/etc/nginx/.htpasswd`)
    
- `/` → kein Auth (JS-Modal übernimmt)
    
- `client_max_body_size 20M` (für Bild-Upload)
    

---

## Docker Container

```
bensn-api           bensn-hub-api         127.0.0.1:5001->5001/tcp   Up
bensn-postgres      postgres:16-alpine    127.0.0.1:5432->5432/tcp   Up (healthy)
weather-collector   weather-stack-...     (kein Port)                 Up
weather-api         weather-stack-api     0.0.0.0:5000->5000/tcp     Up
weather-grafana     grafana/grafana       0.0.0.0:3000->3000/tcp     Up
weather-influxdb    influxdb:2.7          0.0.0.0:8086->8086/tcp     Up
stirling-pdf-1      frooodle/s-pdf        0.0.0.0:8081->8080/tcp     Up (healthy)
```

### Docker Compose Pfade

- Weather Stack: `~/weather-stack/docker-compose.yml`
- bensn-api + postgres: `~/bensn-hub/docker-compose.yml`
- Stirling PDF: `~/stirling-pdf/docker-compose.yml`

---

## Systemd Services

|Service|Status|Beschreibung|
|---|---|---|
|`feed-api.service`|active|`/var/www/feed/api/app.py`, Port 5002|
|`bensn-auth.service`|active|`/var/www/bensn-auth/auth.py`, Port 5003, Gunicorn|
|`nginx.service`|active|Reverse Proxy|
|`docker.service`|active|Container Runtime|
|`cron.service`|active|Vault-Sync + Weather-Collect|

### feed-api.service

```ini
[Unit]
Description=Bensn Feed API
After=network.target

[Service]
WorkingDirectory=/var/www/feed/api
ExecStart=/usr/bin/python3 /var/www/feed/api/app.py
Restart=always
RestartSec=5
```

### bensn-auth.service

```ini
[Unit]
Description=bensn Auth Service
After=network.target

[Service]
User=www-data
WorkingDirectory=/var/www/bensn-auth
ExecStart=/usr/bin/python3 -m gunicorn --workers 1 --bind 127.0.0.1:5003 auth:app
Restart=always
RestartSec=5
```

---

## Datenbank (PostgreSQL)

- Container: `bensn-postgres`
- DB: `bensnos`
- User: `bensn`
- Verbindung vom Host: `docker exec bensn-postgres psql -U bensn -d bensnos`

### Tabellen

|Tabelle|Zweck|Befüllt?|
|---|---|---|
|`shifts`|Arbeitsschichten|✅ aktiv|
|`breaks`|Pausen pro Schicht|✅ aktiv|
|`sleep_logs`|Schlafdaten|⬜ noch leer|
|`health_logs`|Schritte, Gewicht, Meds|⬜ noch leer|
|`mood_logs`|Stimmung, Energie, Angst|⬜ noch leer|
|`location_logs`|GPS-Standorte|⬜ noch leer|
|`obsidian_entries`|Obsidian-Einträge (Mirror)|⬜ noch leer|
|`feed_items`|Kombinierter Feed-Cache|⬜ noch leer|

---

## File-Struktur `/var/www/`

```
/var/www/
├── shared/
│   ├── bensn.css          ← Design System (alle Seiten)
│   └── bensn.js           ← Blob-Animation
├── bensn.me/
│   └── index.html         ← Landing Page
├── bensn-auth/
│   └── auth.py            ← Auth Service (Flask/Gunicorn, Port 5003)
├── worktracker/
│   ├── index.html         ← PWA Frontend
│   ├── eingabe/index.html ← Eingabe-Interface
│   ├── sw.js
│   └── manifest.json
├── tracking/
│   └── index.html         ← Tracking PWA Frontend
├── location/
│   └── index.html         ← Location Frontend
├── feed/
│   ├── api/app.py         ← Flask Backend (feed-api)
│   ├── vault/             ← git clone BensnKnowledge (read-only)
│   ├── share_config.json
│   └── public/
│       ├── index.html     ← Hauptfeed (Cookie-Auth via Nginx)
│       ├── shared.html    ← Geteilter Feed
│       ├── sw.js
│       ├── manifest.json
│       └── uploads/       ← Hochgeladene Bilder (JPEG)
└── html/
    └── index.nginx-debian.html  ← Nginx default (ungenutzt)
```

---

## APIs

### bensn-api (Port 5001) — `api.py`

Auth: `X-API-Key` Header

**Worktracker:**

- `POST /api/shift/start` — Dienst beginnen
- `POST /api/shift/end` — Dienst beenden
- `GET /api/shift/current` — Aktive Schicht + Pausen
- `GET /api/shift/<id>` — Einzelne Schicht
- `GET /api/shifts` — Liste (limit, offset, date)
- `PATCH /api/shift/<id>/correct` — Schicht korrigieren
- `DELETE /api/shift/<id>` — Soft-delete
- `POST /api/break/start` — Pause beginnen
- `POST /api/break/end` — Pause beenden
- `POST /api/break/add` — Pause nachträglich hinzufügen
- `PATCH /api/break/<id>/correct` — Pause korrigieren
- `DELETE /api/break/<id>` — Soft-delete

**Health (Endpoints existieren, DB leer):**

- `POST /api/sleep` — Schlafdaten
- `POST /api/health` — Schritte, Gewicht
- `POST /api/mood` — Stimmungs-Log
- `POST /api/location` — Standort

**Stats:**

- `GET /api/stats/weekly`
- `GET /api/stats/shift-summary`

### feed-api (Port 5002) — `app.py`

Auth: Nginx Basic Auth (außer shared-Endpoints)

- `GET /api/feed` — Alle Obsidian-Notes (privat)
- `GET /api/feed/shared` — Geteilte Notes
- `GET /api/feed/combined` — Notes + Worktracker-Events (privat)
- `GET /api/feed/combined/shared` — Öffentliche kombinierte View
- `GET /api/feed/stats` — Statistiken nach Typ/Folder
- `GET /api/feed/<note_id>` — Einzelne Note
- `POST /api/upload` — Bild-Upload (HEIC/JPEG, max 20MB)
- `GET /api/oembed` — Spotify/YouTube oEmbed Proxy
- `POST /api/webhook` — GitHub Webhook → git sync
- `POST /api/sync` — Manueller git sync

### weather-api (Port 5000)

- `POST /api/location` — iPhone Location POSTs

---

## Obsidian Vault Sync

```
iPhone/Mac (Obsidian + Git Plugin)
  → commit alle ~10min
  → push zu GitHub (BBBensn/BensnKnowledge, privat)
  → GitHub Webhook → POST /api/webhook (sofort)
  → Cron alle 10min: git fetch --all && reset --hard origin/main
     GIT_SSH_COMMAND='ssh -i /root/.ssh/feed_deploy'
```

Vault auf Server: `/var/www/feed/vault/` Journal-Pfad: `/var/www/feed/vault/01_Journal/`

### Note-Typen & Feed-Farben

|Type|Farbe|Hex|Shared?|
|---|---|---|---|
|diary|Sandy Clay|`#e5b181`|✅|
|mood|Celadon|`#b8ebd0`|✅|
|reflexion/reflexionen|Amber Flame|`#ffb400`|✅|
|symptome/symptom|Vibrant Coral|`#f96f5d`|✅|
|therapie|Burnt Rose|`#9c3848`|✅|
|fits/fit|Thistle|`#C9B6BE`|❌|
|arbeit|Pine Teal|`#065143`|❌|
|ideas/idea|Royal Violet|`#6622cc`|❌|
|project_log|Dusk Blue|`#1d4e89`|❌|

### Filename-Konvention

- Häufige Einträge: `YYYY-MM-DD-HHmm-type`
- Tägliche: `YYYY-MM-DD-type`

---

## Design System

Shared via `/shared/bensn.css` + `/shared/bensn.js`

### CSS-Variablen

```css
--bg:           #0a0a0b
--surface:      #111113
--border:       rgba(255,255,255,0.07)
--border-hover: rgba(255,255,255,0.15)
--text:         #e8e6e0
--muted:        #666660
--accent-blue:  #00A6FB
--accent-red:   #FF0051
--green:        #4ade80
--orange:       #e8724a
```

### Fonts

- Display: `Syne` 400/700/800 (Google Fonts)
- Mono: `DM Mono` 400/500 (Google Fonts)

### Landing Page — Kachelfarben

|Service|Klasse|Farbe|Hex|
|---|---|---|---|
|Feed|`card-feed`|Sandy Clay|`#e5b181`|
|Worktracker|`card-wt`|Green|`#4ade80`|
|Stirling PDF|`card-pdf`|Red|`#FF0051`|
|Grafana|`card-data`|Blue|`#00A6FB`|

### Standard Navbar

```html
<nav class="app-nav">
  <a href="https://bensn.me" class="nav-crumb"><span>bensn</span>.me</a>
  <span class="nav-sep">/</span>
  <span class="nav-current">seitenname</span>
  <div class="nav-right">
    <div class="dot" id="statusDot"></div>
    <span id="statusText">laden…</span>
  </div>
</nav>
```

---

## Deploy-Befehle

```bash
# Landing Page
scp index.html root@178.104.133.228:/var/www/bensn.me/index.html

# Worktracker Frontend
scp worktracker.html root@178.104.133.228:/var/www/worktracker/index.html

# Feed Frontend
scp index.html root@178.104.133.228:/var/www/feed/public/index.html

# Feed Backend neu starten
ssh root@178.104.133.228 "systemctl restart feed-api"

# bensn-api (Docker) neu starten
ssh root@178.104.133.228 "docker restart bensn-api"

# Shared CSS/JS
scp bensn.css root@178.104.133.228:/var/www/shared/bensn.css
scp bensn.js root@178.104.133.228:/var/www/shared/bensn.js

# DB-Zugriff
docker exec bensn-postgres psql -U bensn -d bensnos
```

---

## Auth-System (bensn-auth)

Zentrales Cookie-basiertes Auth-System für alle bensn.me Subdomains.

**Funktionsweise:**
- Login unter `auth.bensn.me/auth/login`
- Cookie `bensn_auth` gilt für `.bensn.me` (alle Subdomains), Laufzeit 90 Tage
- Nginx prüft bei jedem Request via `auth_request /auth/verify` → intern Port 5003
- Bei 401: Redirect zu `auth.bensn.me/auth/login?next=<ursprüngliche URL>`
- Nach Login: Redirect zurück zur ursprünglichen URL

**Neue Subdomain schützen (3 Schritte):**
1. DNS A-Record: `subdomain.bensn.me → 178.104.133.228`
2. SSL: `certbot certonly --nginx -d subdomain.bensn.me`
3. Nginx-Config: `auth_request /auth/verify` + `error_page 401 = @bensn_login_redirect` in jeden geschützten `location`-Block

**Ausnahmen (bewusst offen):**
- `POST /api/location` — OwnTracks läuft im Hintergrund ohne Cookie
- `POST /api/upload` — iOS Shortcuts (X-API-Key Auth in Flask)
- `/api/*` auf worktracker/tracking/location — X-API-Key wird von Nginx injiziert

---

## Geplante Services

|Service|Domain|Port|Status|Auth|
|---|---|---|---|---|
|Health Tracker|`health.bensn.me`|5004|🔜 als nächstes|🔒 bensn-auth|
|PC Dashboard|`pc-dashboard.bensn.me`|—|geplant|🔒 bensn-auth|
|Paperless-ngx|`docs.bensn.me`|—|geplant|🔒 bensn-auth|

---

## Bekannte Fallstricke

- `psql` ist am Host nicht installiert → immer via `docker exec bensn-postgres psql ...`
- `db_query` mit `fetchone=True` committed nie → `db_insert` für INSERTs verwenden
- CSS-Variable-Strings werden von `el.style` nicht aufgelöst → `data-active="1"` für State-Detection
- Service Worker Cache: `sw.js` Cache-Version bumpen bei PWA-Updates
- Nginx config für feed: Datei ist `/etc/nginx/sites-enabled/feed.bensn.me` (kein Symlink)
- `git pull --ff-only` schlägt fehl → `fetch --all && reset --hard origin/main` mit `GIT_SSH_COMMAND`
- macOS git case-insensitiv → `core.ignorecase false` + `git rm --cached` bei Duplikaten
- Neue Services: immer zuerst `ss -tlnp | grep PORT` auf Konflikte prüfen
- bensn-auth Logfiles brauchen `www-data` Ownership: `chown www-data:www-data /var/log/bensn-auth*.log`
- Auth-Cookie Domain ist `.bensn.me` → funktioniert nicht auf `localhost` beim lokalen Testen
- TOKEN_SECRET in `auth.py` konstant halten — Änderung loggt alle User aus
