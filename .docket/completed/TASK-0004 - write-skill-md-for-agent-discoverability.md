---
id: TASK-0004
title: Write SKILL.md for agent discoverability
status: Done
created: '2026-03-22'
priority: medium
milestone: MS-0001
tags:
  - agent-native
  - adr-001
definition-of-done:
  - SKILL.md exists at package root
  - describes all commands and their flags
  - lists operational invariants agents should know
  - follows CLI-Anything/Poehnelt patterns from research
visionlog_goal_id: GOAL-006
updated: '2026-03-22'
---
Create SKILL.md following CLI-Anything pattern. Structured markdown that agents read to discover: what apple-a-day does, available commands, output format, invariants (read-only, never requires sudo for basic checks, always returns JSON with --json).

**Completion notes:** SKILL.md at package root. Commands, checks, output format, invariants. Agent-discoverable.
