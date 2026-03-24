---
id: TASK-0017
title: 'Quick actions: run checkup, open report, toggle daemon'
status: To Do
created: '2026-03-24'
priority: medium
tags:
  - macos-app
  - actions
dependencies:
  - TASK-0002
  - TASK-0004
acceptance-criteria:
  - Run Checkup button triggers `aad checkup --json` with spinner
  - Data refreshes after checkup completes
  - Open Report button launches HTML report in browser
  - Daemon toggle shows current state and allows install/uninstall
  - Inline progress feedback (no blocking dialogs)
  - Error states shown inline if CLI fails
visionlog_goal_id: GOAL-010
---
Add action buttons to the panel. "Run Checkup" shells out to `aad checkup --json` with a spinner, refreshes data on completion. "Open Report" shells out to `aad report --html` and opens result in default browser. "Daemon" toggle shows install/uninstall for vitals monitor. All actions fire-and-forget where appropriate (learned from ManyHats SSH tunnel pattern). Show inline progress feedback, not blocking dialogs.
