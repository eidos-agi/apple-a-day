---
id: '0002'
title: 'CLI design for agents: 7 principles from "Rewrite Your CLI for AI Agents"'
status: open
evidence: HIGH
sources: 1
created: '2026-03-22'
---

## Claim

Justin Poehnelt's essay articulates the fundamental design shift: "Human DX optimizes for discoverability and forgiveness. Agent DX optimizes for predictability and defense-in-depth."

**7 design principles for agent-consumed CLIs:**

1. **Raw JSON over custom flags** — agents prefer full API payloads as JSON input, no translation loss
2. **Runtime schema introspection** — expose capabilities queryably at runtime (e.g. `aad schema crash_loops`), not just static docs
3. **Context window discipline** — field masks limit response size, NDJSON for streaming, protect agent context capacity
4. **Adversarial input validation** — "The agent is not a trusted operator." Reject path traversals, control characters, double-encoded strings — agents hallucinate these
5. **Skill files as agent documentation** — structured Markdown (SKILL.md) encoding operational invariants, not `--help` text
6. **Multi-surface exposure** — same capabilities via CLI (humans), MCP (structured JSON-RPC), env vars (headless auth)
7. **Safety rails** — `--dry-run` for mutations, response sanitization against prompt injection in API data

The key insight for apple-a-day: the agent is the primary consumer, but the agent is NOT a trusted operator. Read-only checks are safe; `aad fix` needs the same guardrails as any agent-operated mutation.

## Supporting Evidence

> **Evidence: [HIGH]** — https://justin.poehnelt.com/posts/rewrite-your-cli-for-ai-agents/, retrieved 2026-03-22

## Caveats

None identified yet.
