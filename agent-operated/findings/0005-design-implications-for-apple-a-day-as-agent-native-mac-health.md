---
id: '0005'
title: Design implications for apple-a-day as agent-native Mac health
status: open
evidence: HIGH
sources: 1
created: '2026-03-22'
---

## Claim

Synthesizing all findings, apple-a-day should be designed as:

**Architecture:** Library-first, three surfaces:
1. **Python import** — `from apple_a_day import checkup` — for agents running in-process
2. **CLI with --json** — `aad checkup --json` — for agents shelling out
3. **MCP server** — for Claude Code / MCP-native agents (optional layer)

**Agent-native features to add:**
- `--json` on every command (already have this)
- `--fields` flag to limit response size (protect agent context window)
- `--dry-run` on any future fix commands
- Runtime schema introspection: `aad schema` to list all checks and their output schemas
- SKILL.md co-located with the package for agent discoverability
- Machine-parseable errors (error codes, not prose)

**Trust model (from Agentic SRE pattern):**
- Checks (detect + diagnose) = fully autonomous, no approval needed
- Fixes (act) = policy-gated, human approval by default, agent can request override
- Every fix action logged with before/after state for audit

**What NOT to do:**
- Don't optimize for pretty terminal output over structured data
- Don't assume the caller is human (or trusted)
- Don't require interactive input — agents can't answer prompts

apple-a-day is Agentic SRE for a personal Mac. The framing is: "your Mac's immune system, operated by your AI agent."

## Supporting Evidence

> **Evidence: [HIGH]** — Synthesis of findings 0001-0004 in this research project, retrieved 2026-03-22

## Caveats

None identified yet.
