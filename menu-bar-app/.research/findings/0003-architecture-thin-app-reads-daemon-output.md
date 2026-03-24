---
id: '0003'
title: 'Architecture: thin app reads daemon output'
status: open
evidence: VERIFIED
sources: 1
created: '2026-03-24'
---

## Claim

The app should NOT run health checks itself. It reads daemon output from ~/.config/eidos/aad-logs/ (NDJSON) and shells out to `aad` CLI for on-demand actions. This keeps the app thin and the CLI as source of truth — matching the ManyHats pattern. The app monitors: (1) latest checkup results from log, (2) vitals time-series from vitals.ndjson, (3) daemon status via launchctl. Quick actions: run checkup now, open HTML report, view score, toggle vitals monitor daemon.

## Supporting Evidence

> **Evidence: [VERIFIED]** — ManyHats prior art, apple-a-day architecture (ADR-001 agent-native), retrieved 2026-03-24

## Caveats

None identified yet.
