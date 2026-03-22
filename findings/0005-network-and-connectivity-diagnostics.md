---
id: '0005'
title: Network and connectivity diagnostics
status: open
evidence: MODERATE
sources: 1
created: '2026-03-22'
---

## Claim

Two native tools cover network health:

1. **networkQuality** — Apple's built-in tool (macOS 12+) for network throughput and latency measurement. Simple to invoke, returns structured results. Not yet in apple-a-day.
2. **dns-sd / airport command** — native utilities for debugging Wi-Fi and DNS issues. `airport` is at `/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport`. Can show signal strength, noise, channel, BSSID.

Network is a natural module to add — "is my Mac slow" often turns out to be a network problem, not a compute problem.

## Supporting Evidence

> **Evidence: [MODERATE]** — https://setapp.com/how-to/run-diagnostics-on-mac, retrieved 2026-03-22

## Caveats

None identified yet.
