---
date_created: 2026-09-16 06:28:59
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-16 06:28:59
---

# v2.5.0 — Design-Angleichung an Worktracker (2026-09-16)
- `.entry-action-btn`-Text-Links ("Zeitpunkt ändern", "Löschen") durch `.btn-pill` ersetzt:
  geborderte, großgeschriebene DM-Mono-Buttons, 1:1 aus `worktracker`s "Bearbeiten"/
  "+ Pause"/"Löschen"-Buttons übernommen statt einer eigenen Text-Link-Optik
- Dieselbe `.btn-pill`-Klasse jetzt identisch in `health.bensn.me` — Ziel: eine
  gemeinsame, theme-fähige Komponenten-Sprache über alle bensn.me-Frontends hinweg
- Nebenbei zwei veraltete Hinweise in "Projekt-spezifische Konventionen" korrigiert, die
  noch den (seit v2.3.0 abgeschafften) Obsidian-Dateilesepfad beschrieben
