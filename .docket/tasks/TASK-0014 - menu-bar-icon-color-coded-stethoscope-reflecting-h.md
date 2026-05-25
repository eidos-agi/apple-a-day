---
id: TASK-0014
title: 'Menu bar icon: color-coded stethoscope reflecting health grade'
status: To Do
created: '2026-03-24'
priority: high
tags:
  - macos-app
  - ux
dependencies:
  - TASK-0002
acceptance-criteria:
  - Stethoscope icon renders in menu bar at correct size
  - Icon color changes based on worst health dimension grade
  - Green for A-B, yellow for C, orange for D, red for F, gray for no data
  - Grade letter shown beside icon (e.g. stethoscope + 'A')
  - Updates when HealthService data refreshes
visionlog_goal_id: GOAL-010
---
The menu bar icon should reflect aggregate health status. Use SF Symbol "stethoscope" with color: green (A-B grade), yellow (C), orange (D), red (F). Follow Carbon Design consolidation rule: overall color = worst dimension. When no data available (first launch, daemon not running), show gray. Accessibility: pair color with the grade letter beside the icon when possible (compact text).
