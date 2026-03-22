---
id: TASK-0001
title: 'Drop click, rewrite CLI with argparse'
status: To Do
created: '2026-03-22'
priority: high
milestone: MS-0001
tags:
  - zero-dep
  - adr-002
definition-of-done:
  - aad checkup works with all existing flags
  - click removed from pyproject.toml dependencies
  - all 17 tests pass
visionlog_goal_id: GOAL-007
---
Replace click with stdlib argparse. Same flags: --json, --min-severity, --check, --no-parallel, --version. ADR-002 mandate.
