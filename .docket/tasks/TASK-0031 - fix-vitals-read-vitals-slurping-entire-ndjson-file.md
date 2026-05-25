---
id: TASK-0031
title: Fix vitals read_vitals slurping entire NDJSON file (BRUTAL-003)
status: Done
created: '2026-04-02'
priority: critical
milestone: MS-0003
tags:
  - brutal-forge
  - performance
updated: '2026-04-02'
---
read_vitals() loads up to 5MB into memory and parses all 36K JSON objects to find last 60 minutes. Read backwards from EOF or read line-by-line and stop at cutoff.
