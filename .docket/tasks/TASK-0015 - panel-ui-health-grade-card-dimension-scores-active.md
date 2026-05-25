---
id: TASK-0015
title: 'Panel UI: health grade card, dimension scores, active findings'
status: To Do
created: '2026-03-24'
priority: high
tags:
  - macos-app
  - ux
dependencies:
  - TASK-0002
acceptance-criteria:
  - Overall health grade displayed prominently with color
  - 7 dimension scores shown as rows with letter + color indicator
  - Active findings (warning/critical) listed with severity icons
  - Last checkup timestamp visible
  - Daemon status shown (running/stopped with green/red dot)
  - Inline view pattern — no .sheet() modifiers
visionlog_goal_id: GOAL-010
---
Build the main panel content view using inline view swapping (no .sheet()). Top section: overall grade (large letter + color), last checkup timestamp, daemon status indicator. Middle section: 7 dimension score rows (stability, memory, storage, services, security, infra, network) each with letter grade and color dot. Bottom section: active findings list (warnings/criticals) with severity icon and one-line description. Progressive disclosure: compact by default, expandable for details.
