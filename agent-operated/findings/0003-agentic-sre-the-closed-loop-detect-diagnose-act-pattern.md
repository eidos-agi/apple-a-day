---
id: '0003'
title: 'Agentic SRE: the closed-loop detect-diagnose-act pattern'
status: open
evidence: HIGH
sources: 1
created: '2026-03-22'
---

## Claim

Agentic SRE is an established and growing field (Azure SRE Agent, Komodor, incident.io, NexaStack all shipping products). The architecture is a closed-loop pipeline:

1. **Detect** — continuously analyze telemetry to identify anomalies before they cascade
2. **Diagnose** — RAG + dependency graphs correlate signals, trace root causes to recent changes
3. **Act** — policy-governed agents execute remediation (restarts, rollbacks) and verify fixes against SLOs

**Trust model:** Least-privilege design. Routine fixes (pod restarts) are fully automated. Critical operations (DNS, scaling) require human approval. Every action is auditable and traceable.

**Impact numbers (enterprise):** 60-80% fewer false positives, 50-70% faster incident response, 40-60% less manual intervention, 3x faster diagnosis.

**Translation to apple-a-day:** This is exactly the pattern — detect (crash loops, panics, memory pressure), diagnose (decode panic strings, identify broken dylibs, trace crash-loop causes), act (suggest or execute fixes with policy guardrails). apple-a-day is Agentic SRE for a personal Mac.

The current apple-a-day does detect + diagnose. GOAL-003 (auto-fix) is the "act" phase. The guardrail "read-only by default" maps directly to the least-privilege trust model.

## Supporting Evidence

> **Evidence: [HIGH]** — https://www.unite.ai/agentic-sre-how-self-healing-infrastructure-is-redefining-enterprise-aiops-in-2026/, https://learn.microsoft.com/en-us/azure/sre-agent/overview, retrieved 2026-03-22

## Caveats

None identified yet.
