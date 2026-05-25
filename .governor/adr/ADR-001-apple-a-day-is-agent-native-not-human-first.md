---
id: "ADR-001"
type: "decision"
title: "apple-a-day is agent-native, not human-first"
status: "accepted"
date: "2026-03-22"
relates_to: ["GOAL-002", "GOAL-003", "GUARD-002"]
source_research_id: "117c7991-5983-4dee-bc64-ba50f3021e11"
---

## Context

apple-a-day was initially designed as a CLI tool for humans (`aad checkup` with Rich tables). During the first session, the founder clarified that Eidos AGI builds software that AIs run, not humans. Research into agent-native software design (CLI-Anything/HKU, Poehnelt's agent CLI manifesto, Agentic SRE patterns) confirmed this is an established and growing paradigm.

## Decision

apple-a-day is a **diagnostic library first**, with the AI agent as its primary consumer. Architecture is library → CLI → MCP, not CLI with MCP bolted on.

Key implications:
- Structured JSON output is the contract, rich tables are opt-in
- Zero runtime dependencies (agents run in lean environments)
- SKILL.md for agent discoverability
- Runtime schema introspection (`aad schema`)
- No interactive input — everything via flags/args
- Checks are autonomous, fixes are policy-gated
- The agent is not a trusted operator

## Consequences

- GOAL-002 (MCP server) becomes a thin wrapper, not a separate product
- CLI output priorities shift: JSON first, tables second
- Need to add: `--fields`, `aad schema`, SKILL.md, machine-parseable errors
- Future `aad fix` must implement Agentic SRE trust model (least-privilege, audit trail, human approval by default)
- Python is the right language — agents import it or shell out
- Rich becomes optional dependency, not core
