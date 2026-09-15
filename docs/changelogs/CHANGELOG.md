# feed — Changelog (Archiv-Zusammenfassung v1.0.0–v2.0.2)

> Diese Versionen existierten vorher als volle Datei-Snapshots (`Feed_X.X.X/`-Ordner,
> teils mit weiteren Unter-Snapshots wie `Feed_1.6.3.5/`). Im Zuge des Repo-Restructures
> wurden sie zu dieser Zusammenfassung konsolidiert — vollständige historische Dateien
> bleiben über die Git-Historie des "Initial commit" abrufbar, falls nötig.

## v2.0.0–v2.0.2 (2026-04-29)
- Entfernt: JS-basiertes Login-Overlay (Cookie-Auth via bensn-auth deckt das jetzt serverseitig ab)
- Neu: Wikilink-Statistik-Drawer/Filter-Feature

## v1.7.0–v1.7.9 (2026-04-28)
- Sharing-System (`share_config.json`, `private: true` Frontmatter-Override) fertiggestellt
- Kritischer Bugfix: Share-Tokens wurden serverseitig ignoriert (alle Share-Links zeigten den globalen Feed) — behoben v1.7.5–v1.7.6
- Migration von Nginx Basic Auth auf zentrales `bensn-auth`-Cookie-System (siehe `bensn-meta/auth/bensn-auth-v2`)

## v1.6.0–v1.6.4 (2026-04-17–19)
- Diverse Frontend-Iterationen (Kategorie-Farben, Rendering-Fixes)

## v1.0.0–v1.5.x (2026-04-12–14)
- Initialer Launch: Obsidian-Vault-Sync (Git-Webhook + 10-min-Cron), Grundfunktionen (Notes lesen, Worktracker-Events mergen, Bild-Upload, oEmbed)
