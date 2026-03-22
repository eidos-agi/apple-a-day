---
id: "GOAL-003"
type: "goal"
title: "Auto-fix: opt-in remediation for common issues"
status: "locked"
date: "2026-03-22"
depends_on: []
unlocks: []
---

When a finding has a known fix (e.g. `brew reinstall watchman`, `launchctl bootout`), offer `aad fix` to apply it with confirmation. Non-destructive by default — always confirm before acting.
