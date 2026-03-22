---
id: "GUARD-003"
type: "guardrail"
title: "Plain english, always actionable"
status: "active"
date: "2026-03-22"
---

## Rule
Every finding must include a human-readable summary and a concrete fix or next step. Never surface raw error codes or log lines without interpretation.

## Why
The whole point of this tool is translating macOS diagnostics into answers. If the user still has to Google the output, we failed.

## Violation Examples
- Reporting "exit code -6" without explaining it means SIGABRT
- Showing a panic string without decoding the cause
- A WARNING finding with no `fix` field
