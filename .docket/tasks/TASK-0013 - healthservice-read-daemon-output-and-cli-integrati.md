---
id: TASK-0013
title: 'HealthService: read daemon output and CLI integration'
status: To Do
created: '2026-03-24'
priority: high
tags:
  - macos-app
  - backend
dependencies:
  - TASK-0001
acceptance-criteria:
  - Parses latest checkup NDJSON entry into Swift struct
  - Parses recent vitals samples (load, thermal, memory) from vitals.ndjson
  - Detects daemon running/stopped via launchctl
  - Shells out to `aad score --json` and parses 7-dimension grades
  - Provides runCheckup() and openReport() methods that call aad CLI
  - Auto-refreshes on panel open
visionlog_goal_id: GOAL-010
---
Create a HealthService class (ObservableObject) that: (1) reads the latest checkup entry from `~/.config/eidos/aad-logs/` NDJSON, (2) reads recent vitals samples from vitals.ndjson, (3) checks daemon status via `launchctl list | grep apple-a-day`, (4) shells out to `aad score --json` for health grades, (5) provides methods to trigger checkup/report via CLI. The app is a thin observer — all intelligence stays in the Python CLI.
