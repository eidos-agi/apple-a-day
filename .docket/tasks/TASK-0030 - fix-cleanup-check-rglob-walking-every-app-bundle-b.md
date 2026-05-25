---
id: TASK-0030
title: Fix cleanup check rglob walking every app bundle (BRUTAL-002)
status: Done
created: '2026-04-02'
priority: critical
milestone: MS-0003
tags:
  - brutal-forge
  - performance
updated: '2026-04-02'
---
_find_stale_apps() calls rglob("*") on every app in /Applications — millions of FS ops. Replace with du -sk subprocess call or drop app size from scoring.
