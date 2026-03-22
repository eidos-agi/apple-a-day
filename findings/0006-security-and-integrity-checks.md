---
id: '0006'
title: Security and integrity checks
status: open
evidence: MODERATE
sources: 1
created: '2026-03-22'
---

## Claim

macOS has native security primitives apple-a-day should surface:

1. **csrutil** — System Integrity Protection status. Should always be enabled; if disabled, it's a critical finding.
2. **spctl** — Gatekeeper assessment. Checks app notarization status.
3. **XProtect** — Apple's built-in malware definitions. Can check version/freshness to ensure definitions are current.
4. **Mac Monitor (Endpoint Security)** — uses Apple's Endpoint Security framework for deep process/file/network telemetry. Overkill for apple-a-day but good reference for security-focused checks.

A simple security module checking SIP status, Gatekeeper, XProtect freshness, and FileVault status would cover the basics without reimplementing Mac Monitor.

## Supporting Evidence

> **Evidence: [MODERATE]** — https://setapp.com/how-to/run-diagnostics-on-mac, https://github.com/Brandon7CC/mac-monitor, retrieved 2026-03-22

## Caveats

None identified yet.
