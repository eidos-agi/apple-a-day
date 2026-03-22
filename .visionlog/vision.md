---
title: "apple-a-day: Agent-Native Mac Health"
type: "vision"
date: "2026-03-22"
---

**Your Mac's immune system, operated by your AI agent.**

apple-a-day is an agent-native Mac health library. It detects crashes, diagnoses root causes, and enables autonomous remediation — designed to be called by AI agents, not just typed by humans.

## Why This Exists

Eidos AGI builds software that AIs run, not humans. An AI agent operating on a Mac needs to know if its host is healthy, why a service crashed, whether memory pressure is killing performance, and what to do about it. Today that requires 20 minutes of manual forensics across scattered macOS diagnostic tools. apple-a-day answers "what's wrong with this Mac?" in one call.

## Architecture: Library First

apple-a-day is a **diagnostic library** with multiple thin surfaces:

1. **Python import** (primary) — `from apple_a_day import checkup` — for agents running in-process
2. **CLI** — `aad checkup --json` — for agents shelling out, `aad checkup` for humans demoing
3. **MCP server** (optional) — for Claude Code / MCP-native agent frameworks

The library doesn't care who's calling it or how. It returns structured `CheckResult` and `Finding` objects. The caller decides what to do.

## Agent-Native Design Principles

Following the established agent-native patterns (CLI-Anything/HKU, Poehnelt's agent CLI manifesto):

1. **Structured output is the contract** — JSON by default for agents, rich tables opt-in for humans
2. **Self-describing** — runtime schema introspection via `aad schema`, SKILL.md for agent discovery
3. **The agent is not a trusted operator** — checks are read-only (safe), fixes require policy gates
4. **Context window discipline** — `--fields` flag limits response size, findings are concise
5. **No interactive input** — agents can't answer prompts, everything via flags/args
6. **Multi-surface** — same logic via import, CLI, and MCP

## The Agentic SRE Pattern

apple-a-day implements the detect → diagnose → act loop from Agentic SRE, applied to a personal Mac:

| Phase | What apple-a-day Does | Autonomy Level |
|-------|----------------------|----------------|
| **Detect** | Crash loops, kernel panics, memory pressure, disk health, broken dylibs, rogue services | Fully autonomous |
| **Diagnose** | Decode panic strings, trace crash-loop causes, identify missing libraries, explain in plain english | Fully autonomous |
| **Act** | Suggest fixes with commands; execute with policy gates and audit trail | Human-approved by default |

## Core Principles

1. **Mac-native** — uses macOS-specific tools directly (otool, diskutil, launchctl, powermetrics). No cross-platform.
2. **Zero runtime dependencies** — stdlib Python only. Agents run in lean environments.
3. **Plain english, always actionable** — every finding has a severity, explanation, and fix.
4. **Read-only by default** — checks never modify system state. Fixes require explicit opt-in.
5. **Agent-first, human-friendly** — structured data for agents, pretty output for humans. Same library.

## Target Consumers

1. AI agents (Eidos, Claude Code, any agent framework) — primary
2. Mac developers running `aad checkup` — secondary
3. SRE/ops agents monitoring fleet Macs — future
