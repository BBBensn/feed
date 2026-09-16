---
date_created: 2026-09-16 22:44:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-16 22:44:00
---

# v2.5.1 — Design-System zentralisiert (2026-09-16)
- `.btn-pill`, `.btn-save`, `.btn-cancel` aus dem lokalen `<style>`-Block entfernt — kommen
  jetzt aus dem neu versionierten `bensn-meta/shared/bensn.css`, das identisch von
  health/tracking eingebunden wird. Keine sichtbare Änderung, reine Konsolidierung gegen
  Drift zwischen den Apps
