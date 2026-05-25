---
id: "GOAL-003"
type: "goal"
title: "Auto-fix: opt-in remediation for common issues"
status: "locked"
date: "2026-03-22"
depends_on: []
unlocks: []
---

Per ADR-001 and Agentic SRE research: implement the "act" phase of detect→diagnose→act. Fixes are policy-gated: human approval by default, agent can request override. Every fix logged with before/after state for audit. `--dry-run` required on all mutations. The agent is not a trusted operator.
