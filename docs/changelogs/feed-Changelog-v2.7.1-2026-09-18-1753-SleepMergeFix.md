---
date_created: 2026-09-18 17:53:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-18 17:53:00
---

# v2.7.1 — Oura-Schlaf-Merge korrigiert (2026-09-18)
- `fetch_sleep_events()` fasste bisher alle Perioden mit gleichem Oura-`day`-Wert zusammen —
  mit echten Daten verifiziert erwies sich das als falsch: Oura vergibt denselben `day`
  manchmal an zwei komplett unabhängige Nächte (~24h auseinander) oder eine Nacht plus einen
  viel späteren Tages-Nap. Das führte zu Unsinn wie einer "15,6h-Nacht" aus zwei echten,
  getrennten Nächten
- Jetzt zeitbasierte Cluster-Erkennung: Perioden werden nur zusammengefasst, wenn der
  Abstand zwischen ihnen klein genug ist, um plausibel "kurz aufgewacht, weitergeschlafen"
  zu sein (`SLEEP_CLUSTER_GAP` = 3 Stunden) — größere Lücken werden zu eigenen Feed-Events,
  auch wenn Oura denselben `day` vergeben hat
- Synchron zu derselben Korrektur in health-apis `_merge_nightly_sleep()`
