---
id: TASK-0003
title: 'Add runtime schema introspection: aad schema'
status: To Do
created: '2026-03-22'
priority: high
milestone: MS-0001
tags:
  - agent-native
  - adr-001
definition-of-done:
  - aad schema outputs valid JSON describing all 7 checks
  - each check lists its possible finding fields
  - agents can discover capabilities without reading README
visionlog_goal_id: GOAL-006
---
Add `aad schema` command that outputs JSON schema of all checks: name, description, output fields, severity levels. Agents use this to understand what apple-a-day can do at runtime without consuming docs tokens.
