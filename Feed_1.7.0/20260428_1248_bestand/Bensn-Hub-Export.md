---
date_created: 2026-04-20 02:52:47
type: codebin
sprache: 
tags: [codebin]
date_modified: 2026-04-20 02:57:03
---

# Bensn-Hub-Export

## Zweck
Schneller Export aller relevanter Files von [[Bensn-Hub]].

## Code

```bash


#!/bin/bash
# bensn-export.sh — Snapshot aller relevanten Projektfiles
# Ausführen: bash /root/bensn-export.sh
# Ergebnis: /root/export/bensn-DATUM.tar.gz

EXPORT_DIR="/root/export"
DATE=$(date +%Y-%m-%d)
SNAP="$EXPORT_DIR/bensn-$DATE"

mkdir -p "$SNAP"

# ── Shared Design System ──
mkdir -p "$SNAP/shared"
cp /var/www/shared/bensn.css "$SNAP/shared/"
cp /var/www/shared/bensn.js "$SNAP/shared/"

# ── Landing ──
mkdir -p "$SNAP/landing"
cp /var/www/bensn.me/index.html "$SNAP/landing/"

# ── Worktracker Frontend ──
mkdir -p "$SNAP/worktracker"
cp /var/www/worktracker/index.html "$SNAP/worktracker/"
cp /var/www/worktracker/sw.js "$SNAP/worktracker/"
cp /var/www/worktracker/manifest.json "$SNAP/worktracker/"
cp /var/www/worktracker/eingabe/index.html "$SNAP/worktracker/eingabe.html"

# ── Feed Frontend + API ──
mkdir -p "$SNAP/feed"
cp /var/www/feed/public/index.html "$SNAP/feed/"
cp /var/www/feed/public/sw.js "$SNAP/feed/"
cp /var/www/feed/public/manifest.json "$SNAP/feed/"
cp /var/www/feed/public/shared.html "$SNAP/feed/"
cp /var/www/feed/api/app.py "$SNAP/feed/"
cp /var/www/feed/share_config.json "$SNAP/feed/"

# ── Location ──
mkdir -p "$SNAP/location"
cp /var/www/location/index.html "$SNAP/location/"

# ── Bensn-Hub Backend ──
mkdir -p "$SNAP/bensn-hub"
cp /root/bensn-hub/api.py "$SNAP/bensn-hub/"
cp /root/bensn-hub/docker-compose.yml "$SNAP/bensn-hub/"
cp /root/bensn-hub/schema.sql "$SNAP/bensn-hub/"
cp /root/bensn-hub/requirements.txt "$SNAP/bensn-hub/"
cp /root/bensn-hub/geocode.py "$SNAP/bensn-hub/"
cp /root/bensn-hub/weather_location.py "$SNAP/bensn-hub/"
# .env bewusst NICHT exportiert (Secrets)

# ── Weather Stack ──
mkdir -p "$SNAP/weather-stack"
cp /root/weather-stack/docker-compose.yml "$SNAP/weather-stack/"
cp /root/weather-stack/api/api.py "$SNAP/weather-stack/"
cp /root/weather-stack/api/requirements.txt "$SNAP/weather-stack/"
cp /root/weather-stack/collector/collector.py "$SNAP/weather-stack/"
cp /root/weather-stack/collector/requirements.txt "$SNAP/weather-stack/collector-requirements.txt"
cp /root/weather-stack/collector/crontab "$SNAP/weather-stack/"

# ── Stirling PDF Config ──
mkdir -p "$SNAP/stirling-pdf"
cp /root/stirling-pdf/docker-compose.yml "$SNAP/stirling-pdf/"
cp /root/stirling-pdf/extraConfigs/settings.yml "$SNAP/stirling-pdf/"
cp /root/stirling-pdf/extraConfigs/custom_settings.yml "$SNAP/stirling-pdf/" 2>/dev/null || true

# ── Nginx Configs ──
mkdir -p "$SNAP/nginx"
for f in /etc/nginx/sites-enabled/*; do
  cp "$(realpath "$f")" "$SNAP/nginx/$(basename "$f")"
done

# ── Systemd Services ──
mkdir -p "$SNAP/systemd"
for svc in feed-api; do
  f="/etc/systemd/system/$svc.service"
  [ -f "$f" ] && cp "$f" "$SNAP/systemd/"
done

# ── Tar it up ──
cd "$EXPORT_DIR"
tar -czf "bensn-$DATE.tar.gz" "bensn-$DATE/"
rm -rf "$SNAP"

echo "✓ Export fertig: $EXPORT_DIR/bensn-$DATE.tar.gz"
ls -lh "$EXPORT_DIR/bensn-$DATE.tar.gz"


```

## Verwendung
Wie wird es ausgeführt? Welche Parameter?

## Voraussetzungen
- 

## Notizen
