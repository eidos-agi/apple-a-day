---
id: TASK-0019
title: CLI validation + empty/error state views
status: To Do
created: '2026-03-24'
priority: high
tags:
  - macos-app
  - ux
  - error-handling
dependencies:
  - TASK-0012
acceptance-criteria:
  - App checks for aad binary on launch (pyenv shims, /usr/local/bin, PATH)
  - CLI-not-found state shows install instructions
  - No-data state shows 'Run first checkup?' with action button
  - CLI error state shows inline error message
  - Version check warns if CLI version is unexpected
  - States are inline views (not alerts or sheets)
visionlog_goal_id: GOAL-010
---
On app launch, validate that the `aad` CLI is findable and functional. Check common paths (~/.pyenv/shims/aad, /usr/local/bin/aad, etc.) and verify with `aad --version`. Handle three failure modes: (1) CLI not found — show "apple-a-day CLI not installed" with install instructions, (2) no log data yet — show "No checkup data. Run your first checkup?" with a button, (3) CLI error — show inline error message. These states replace the main panel content gracefully rather than showing broken/empty UI.
