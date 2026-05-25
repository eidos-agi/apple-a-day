---
id: TASK-0005
title: Add --fields flag for context window discipline
status: Done
created: '2026-03-22'
priority: medium
milestone: MS-0001
tags:
  - agent-native
  - adr-001
definition-of-done:
  - '--fields severity,summary returns only those fields in JSON'
  - works with --json flag
  - invalid field names return a clear error
visionlog_goal_id: GOAL-006
updated: '2026-03-22'
---
Add --fields flag to limit which fields are returned in JSON output (e.g. --fields severity,summary,fix). Agents use this to keep responses small and protect their context window.

**Completion notes:** --fields flag filters JSON output fields. Tested: --fields severity,summary,fix correctly strips check and details.
