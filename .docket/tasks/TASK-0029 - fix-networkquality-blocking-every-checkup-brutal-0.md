---
id: TASK-0029
title: Fix networkQuality blocking every checkup (BRUTAL-001)
status: Done
created: '2026-04-02'
priority: critical
milestone: MS-0003
tags:
  - brutal-forge
  - performance
updated: '2026-04-02'
---
networkQuality runs a full bandwidth test (30s timeout, consumes metered bandwidth) on every checkup. Split into check_network_wifi() (fast, always) and check_network_speed() (opt-in). Or add --skip-speedtest flag.
