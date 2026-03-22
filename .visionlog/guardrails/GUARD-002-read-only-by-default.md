---
id: "GUARD-002"
type: "guardrail"
title: "Read-only by default"
status: "active"
date: "2026-03-22"
---

## Rule
All checks are read-only. No check module may modify system state. Fixes require explicit user opt-in via a separate `fix` command with confirmation.

## Why
A health tool that breaks things is worse than no tool. Users must trust that running `aad checkup` is always safe.

## Violation Examples
- A check module that kills a process
- Auto-running `brew reinstall` during a checkup
- Modifying plist files without explicit confirmation
