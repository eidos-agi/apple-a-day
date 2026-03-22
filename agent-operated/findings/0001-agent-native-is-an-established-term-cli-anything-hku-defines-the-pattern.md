---
id: '0001'
title: '"Agent-native" is an established term — CLI-Anything (HKU) defines the pattern'
status: open
evidence: HIGH
sources: 1
created: '2026-03-22'
---

## Claim

CLI-Anything (HKU Data Intelligence Lab, github.com/HKUDS/CLI-Anything) has formalized the concept of "agent-native software" with a clear definition and architecture:

**Definition:** Agent-native software operates through structured, machine-parseable command interfaces rather than GUI automation or fragmented APIs. "Today's Software Serves Humans. Tomorrow's Users will be Agents."

**Four properties of agent-native tools:**
1. **Deterministic & Reliable** — consistent output enables predictable agent behavior
2. **Self-Describing** — `--help` flags provide automatic documentation agents can discover
3. **Structured & Composable** — text commands match LLM format and chain for workflows
4. **Lightweight & Universal** — minimal overhead, works across systems without dependencies

**Key artifacts:**
- Every command has a `--json` flag for machine consumption
- SKILL.md files co-located with the CLI for agent discoverability
- HARNESS.md as a methodology SOP for how CLIs should be structured
- Persistent state with undo/redo for agent error recovery

This is the closest existing framework to what apple-a-day should be. The term "agent-native" is the right label for what Eidos AGI is building.

## Supporting Evidence

> **Evidence: [HIGH]** — https://github.com/HKUDS/CLI-Anything, https://clianything.org/, retrieved 2026-03-22

## Caveats

None identified yet.
