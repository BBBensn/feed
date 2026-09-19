# Bensn-Feed — CLAUDE.md

Projekt-spezifischer Kontext. Ergänzt `~/.claude/CLAUDE.md`.
Ablageort: `~/Documents/Coding/bensn-hub/feed/CLAUDE.md`

---

## Projekt-Basics

- **Name:** Bensn-Feed
- **Domain:** feed.bensn.me
- **Version:** v2.7.3 (Service-Worker-Bugfix für Safari/Mobilfunk)
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
ein zweites HTTP-Client-Pattern wäre unnötig gewesen.

Seit v2.7.0 (2026-09-17) zusätzlich: `fetch_medication_note_events()` (zeitgestempelte
Wirkungs-/Nebenwirkungsbeobachtungen aus `health_medication_effect_notes`, JOIN über
`health_medication_logs`→`health_medications` für den Medikamentennamen) und
`fetch_weight_events()` (`health_weight_logs`). Beide fehlten bis dahin komplett im Feed,
obwohl "wie hat das Medikament gewirkt" genau die Anmerkungen braucht, nicht nur die
Einnahme selbst.

Alles nur in `feed_combined()` gemergt (privat), nicht in den beiden Shared-Varianten.

---

## Tracking-Integration (`tracking.bensn.me`)

Seit v2.6.0 (2026-09-17): `fetch_tracking_events()` in `api/app.py` liest `tracking_entries`
direkt aus Postgres, gleiches Muster wie die Health-Integration oben. Nur
`entry_type = 'zaehler'` wird als Feed-Event gezeigt (Konsum-/Zähler-Momente wie Red Bull,
Zigarette, Ofen) — `auffuellung`/`entnahme`/`delta` (Vorrat-Buchhaltung, seit tracking
v1.6.0 ohnehin nur noch Hintergrundfunktion) sind keine "Momente", die im Feed auftauchen
sollen. Nur in `feed_combined()` gemergt (privat) — Konsumdaten sind genauso privat wie
Medikamente/Blutdruck.

---

## Oura-Integration (über `health.bensn.me`)

Seit v2.7.0 (2026-09-17): `fetch_sleep_events()` liest `health_oura_sleep`
(Event-Zeitpunkt = `bedtime_end`/Aufwachzeit, nicht `bedtime_start` — man reflektiert über
eine Nacht am Morgen danach, nicht während sie noch läuft). `fetch_heartrate_summary_events()`
liest `health_oura_heartrate` **aggregiert auf einen Wert pro Tag** (Ruhepuls + Min/Max) —
die rohen ~2000 Samples/Tag sind ein kontinuierlicher Datenstrom, kein "Moment", und würden
den Feed fluten. Der Tages-Wert bekommt einen synthetischen Mittags-Zeitstempel
(`YYYY-MM-DDT12:00:00`), da er sich auf den ganzen Tag bezieht, nicht auf einen Augenblick.
Nur in `feed_combined()` gemergt (privat).

**Korrektur v2.7.1 (2026-09-18):** `fetch_sleep_events()` fasste anfangs alle Perioden mit
gleichem Oura-`day`-Wert zusammen — das erwies sich als falsch: Oura vergibt denselben `day`
teils an zwei komplett unabhängige Nächte oder eine Nacht + einen viel späteren Tages-Nap
(mit echten Daten verifiziert). Jetzt zeitbasierte Cluster-Erkennung (`SLEEP_CLUSTER_GAP`,
3 Stunden) statt reinem `day`-Gruppieren — dieselbe Logik wie in health-api's
`_merge_nightly_sleep()`, siehe dessen CLAUDE.md-Eintrag für die volle Herleitung.

---

## Event-Typ-Registry (Frontend, seit v2.7.0)

`SERVICE_EVENTS` in `index.html` ist die einzige Quelle für Farbe/Label/Filter-Gruppe/Render-
Body jedes "von einem anderen Service geschriebenen" Event-Typs (aktuell: `medication_taken`,
`medication_note`, `bp_reading`, `meal_logged`, `weight_logged`, `tracking_logged`,
`sleep_logged`, `heartrate_summary`). `typeColor()`, `typeLabel()`, `renderNote()`s Dispatch
und `typeMatches()` schlagen alle zuerst in dieser Registry nach, bevor sie auf die
alten, type-spezifischen Maps zurückfallen (die nur noch native Journal-Typen und
`work_start`/`work_pause`/`work_end` enthalten — die rendern über eigene, reichhaltigere
Pfade und passen nicht ins generische "Badge + einfacher Body"-Schema).

**Warum:** Vor diesem Refactor musste jeder neue Event-Typ an 8 Stellen einzeln eingetragen
werden (Backend-Fetch, `feed_combined()`-Wiring, CSS-Farbvariable, Filter-Button-HTML,
`typeColor`-Map, `typeLabel`-Map, Render-Dispatch, Filter-Matcher) — genau deshalb fehlten
Medikamenten-Anmerkungen/Gewicht/Schlaf so lange im Feed. Jetzt: ein neuer Typ innerhalb
einer bestehenden Gruppe (health/tracking/oura) = **eine** `SERVICE_EVENTS`-Zeile, Farben und
CSS werden zur Laufzeit aus der Registry generiert (`injectServiceEventStyles()`). Nur eine
komplett neue GRUPPE (z.B. künftig `location`) braucht noch einen manuellen Filter-Button
plus eine `--c-*`-Farbvariable — das ist der bewusst verbleibende, seltene Rest-Aufwand.

Backend-seitig existiert das Äquivalent als `PRIVATE_EVENT_FETCHERS`-Liste in `api/app.py` —
eine neue Quelle ist `fetch_X_events(limit)` schreiben + an die Liste anhängen, kein Suchen
mehr nach der `feed_combined()`-Stelle, die geändert werden muss.

---

## Git

- **Repo:** `git@github.com:BBBensn/feed.git`

---

## Projekt-spezifische Konventionen

- Backend liest ausschließlich aus `journal_entries` (Postgres) — kein Obsidian-Lesepfad
  mehr seit v2.3.0, siehe "Obsidian Vault Sync — abgeschaltet" oben
- `journal_row_to_note()` mappt DB-Zeilen auf dasselbe Shape, das früher `load_note()` aus
  Obsidian-Dateien baute (type/title/content/date/tags/meta) — Altlast aus der Migration,
  aber beibehalten, weil der ganze Feed-Renderer darauf aufbaut und ein Umbenennen keinen
  echten Wert hätte
- **Design-Sprache:** kleine Aktions-Buttons (Zeitpunkt ändern, Löschen) sind `.btn-pill` —
  geborderte, großgeschriebene DM-Mono-Buttons, 1:1 aus `worktracker`s "Bearbeiten"/
  "+ Pause"/"Löschen"-Buttons übernommen. `.btn-pill`/`.btn-save`/`.btn-cancel` liegen seit
  2026-09-16 zentral in `bensn-meta/shared/bensn.css` (vorher hier + in `health`/`tracking`
  fast-identisch dupliziert) — hier lokal NICHT mehr neu definieren. Vollständiger
  Style-Guide (alle Farben/Komponenten live + bekannte Inkonsistenzen):
  `bensn-meta/design-system.html`
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
| v2.5.0 | `.entry-action-btn`-Text-Links durch `.btn-pill` ersetzt (geborderte, großgeschriebene DM-Mono-Buttons, 1:1 aus `worktracker`s Bearbeiten/+Pause/Löschen übernommen) — Teil einer service-übergreifenden Design-Angleichung, dieselbe Klasse existiert jetzt identisch in `health.bensn.me` | ✅ deployed (2026-09-16) |
| v2.5.1 | `.btn-pill`/`.btn-save`/`.btn-cancel` aus lokalem CSS entfernt, kommen jetzt zentral aus `bensn-meta/shared/bensn.css` — keine visuelle Änderung, reine Konsolidierung | ✅ deployed (2026-09-16) |
| v2.6.0 | Tracking-Integration: `tracking_entries` (nur `entry_type='zaehler'`, also Konsum-Momente wie Red Bull/Zigarette/Ofen) erscheinen jetzt im privaten Feed, eigener `tracking`-Filter-Chip + eigene Akzentfarbe (`--c-tracking`, Lime — passend zu tracking.bensn.mes Landing-Page-Farbe) | ✅ deployed (2026-09-17) |
| v2.7.0 | Medikamenten-Anmerkungen, Gewicht und Oura-Schlaf (+ Oura-Herzfrequenz als Tages-Zusammenfassung) erscheinen jetzt im Feed — die größte fehlende Lücke für ein "vollständiges Alltagsbild". Gleichzeitig Event-Typ-Registry eingeführt (`SERVICE_EVENTS` im Frontend, `PRIVATE_EVENT_FETCHERS` im Backend), damit ein neuer Typ nicht mehr an 8 verstreuten Stellen einzeln nachgezogen werden muss (genau das war der Grund, warum diese drei Quellen so lange fehlten) | ✅ deployed (2026-09-17) |
| v2.7.1 | Bugfix: `fetch_sleep_events()` fasste Perioden fälschlich nach Oura's `day`-Feld zusammen (verschmolz teils zwei unabhängige Nächte) — jetzt zeitbasierte Cluster-Erkennung (`SLEEP_CLUSTER_GAP`, 3h), synchron zu health-apis `_merge_nightly_sleep()` | ✅ deployed (2026-09-18) |
| v2.7.2 | `fetch_bp_events()` selektiert jetzt `notes` mit, `bp_reading`-Event im Frontend zeigt sie als zusätzliche Zeile — Notizen zu einer Blutdruckmessung waren speicherbar, aber bisher weder hier noch in `health.bensn.me`s Verlauf sichtbar | ✅ deployed (2026-09-18) |
| v2.7.3 | Bugfix: Service Worker konnte auf Safari/Mobilfunk komplett ausfallen ("FetchEvent.respondWith received an error: Returned response is null") — `fetch(...).catch(() => caches.match(...))` resolvte bei Netzwerkfehler + Cache-Miss zu `undefined`, was WebKit als fatalen Fehler wertet (Chromium verzeiht das). Bei `feed` besonders sichtbar, weil hier (anders als `health`/`tracking`) auch `/api/`-GETs vom Service Worker abgefangen werden. Cache-Fallback gibt jetzt immer ein echtes Response-Objekt zurück, notfalls eine 503-Antwort. Gleicher Fix in `health`/`tracking` (identischer sw.js-Code) | ✅ deployed (2026-09-19) |

Details zur vollständigen Versionshistorie: `docs/changelogs/CHANGELOG.md`.

---

## Obsidian-Doku

- Projekt-MD: `03_Projects/Coding PC/Bensn-Hub/Feed/Feed.md`
- Changelogs: `03_Projects/Coding PC/Bensn-Hub/Feed/Changelogs/`
