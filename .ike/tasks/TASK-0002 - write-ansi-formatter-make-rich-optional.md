---
id: TASK-0002
title: 'Write ANSI formatter, make rich optional'
status: To Do
created: '2026-03-22'
priority: high
milestone: MS-0001
tags:
  - zero-dep
  - adr-002
definition-of-done:
  - aad checkup renders colored output without rich installed
  - 'pip install apple-a-day[rich] enables rich tables'
  - rich removed from core dependencies
  - zero entries in dependencies list
visionlog_goal_id: GOAL-007
---
Write a thin ANSI escape code + Unicode box-drawing formatter as default renderer. Move rich to optional extra: pip install apple-a-day[rich]. Auto-detect: if rich is importable, use it; otherwise ANSI.
