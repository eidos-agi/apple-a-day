---
title: "apple-a-day: Mac Health Toolkit"
type: "vision"
date: "2026-03-22"
---

**An apple a day keeps the doctor away.**

apple-a-day is a Mac-native health toolkit for developers and power users. It monitors, diagnoses, and fixes common macOS issues before they cascade into crashes, data loss, or wasted hours debugging.

## Why This Exists

Macs have rich built-in diagnostic tools — `memory_pressure`, `powermetrics`, `sysctl`, `diskutil`, `otool`, DiagnosticReports, `launchctl` — but nobody uses them because they're scattered, low-level, and produce raw output. A crash-looping Homebrew service can cause kernel panics for days before anyone notices.

apple-a-day wraps these native tools into a single checkup that speaks plain english.

## Core Principles

1. **Mac-native, Mac-specific** — no cross-platform abstraction. We use macOS APIs and tools directly.
2. **Plain-english output** — don't just report "exit code -6", explain what it means and how to fix it.
3. **Actionable** — every finding includes a fix command or next step.
4. **Non-destructive** — read-only by default. Fixes require explicit opt-in.
5. **MCP-native** — any Claude session can query Mac health as a tool.

## Surface Area

| Module | What It Watches |
|--------|----------------|
| Crash Loops | DiagnosticReports for processes dying repeatedly |
| Kernel Panics | Panic logs decoded into human-readable causes |
| Dylib Health | Broken dynamic library links after brew upgrades |
| Memory Pressure | RAM pressure, swap usage, leak indicators |
| Disk Health | APFS state, free space, Time Machine snapshot bloat |
| Launch Agents | Rogue/crashed/forgotten launchd services |
| Homebrew | Outdated packages, doctor warnings, orphans |

## Interfaces

- **CLI**: `aad` command — run `aad checkup` for a full report
- **MCP Server**: Any Claude Code session can call health checks as tools
- **JSON output**: `aad checkup --json` for programmatic consumption

## Target Users

- Eidos AGI developers (our own Macs first)
- Mac power users and sysadmins
- Anyone who's ever asked "why does my Mac keep crashing?"
