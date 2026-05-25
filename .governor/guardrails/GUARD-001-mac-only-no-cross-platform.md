---
id: "GUARD-001"
type: "guardrail"
title: "Mac-only, no cross-platform"
status: "active"
date: "2026-03-22"
---

## Rule
All code must target macOS exclusively. No Linux/Windows compatibility layers, no cross-platform abstractions, no `platform.system()` branching.

## Why
The value of this tool is deep macOS integration. Cross-platform dilutes that into mediocrity. Use `otool`, `diskutil`, `launchctl`, `powermetrics` — not portable alternatives.

## Violation Examples
- Adding `if platform.system() == "Darwin"` guards
- Using `psutil` instead of native macOS commands
- Adding Windows/Linux check modules
