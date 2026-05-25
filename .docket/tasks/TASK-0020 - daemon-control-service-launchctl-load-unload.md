---
id: TASK-0020
title: Daemon control service (launchctl load/unload)
status: To Do
created: '2026-03-24'
priority: medium
tags:
  - macos-app
  - daemon
dependencies:
  - TASK-0013
acceptance-criteria:
  - Detects vitals monitor daemon status (loaded/running/stopped)
  - Detects daily checkup daemon status
  - Can load vitals daemon via launchctl
  - Can unload vitals daemon via launchctl
  - Handles permission errors gracefully with user-facing message
  - Status shown with green/red indicator in panel
visionlog_goal_id: GOAL-010
---
Implement daemon lifecycle management. The app needs to: (1) detect if the vitals monitor daemon is loaded via `launchctl list | grep apple-a-day`, (2) load the daemon plist via `launchctl load`, (3) unload via `launchctl unload`, (4) detect if the daily checkup daemon is active. Show daemon status in the panel (running/stopped) and provide toggle controls. Handle permission issues gracefully — launchctl may require the plist to be in ~/Library/LaunchAgents/.
