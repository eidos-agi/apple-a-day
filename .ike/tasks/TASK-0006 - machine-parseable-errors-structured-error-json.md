---
id: TASK-0006
title: Machine-parseable errors (structured error JSON)
status: To Do
created: '2026-03-22'
priority: medium
milestone: MS-0001
tags:
  - agent-native
  - adr-001
definition-of-done:
  - 'errors return JSON with error_code, message, suggestion fields'
  - no Python tracebacks in --json mode
  - >-
    agents can distinguish between 'check found problems' and 'check itself
    failed'
visionlog_goal_id: GOAL-006
---
When a check fails to run (permission denied, tool not found, timeout), return structured JSON error with error_code, message, and suggestion — not a Python traceback or prose string. Agents need to parse errors programmatically.
