---
id: TASK-0032
title: Cap ThreadPoolExecutor workers and group slow checks (BRUTAL-004)
status: Done
created: '2026-04-02'
priority: critical
milestone: MS-0003
tags:
  - brutal-forge
  - performance
updated: '2026-04-02'
---
13 threads spawned simultaneously with heavy I/O. Cap at 4-6 workers. Group fast checks (sysctl-based) and slow checks (network, homebrew, cleanup) separately.
