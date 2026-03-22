---
id: '0003'
title: 'Disk, storage, and backup tools'
status: open
evidence: HIGH
sources: 1
created: '2026-03-22'
---

## Claim

Three tools/patterns cover disk and storage health:

1. **diskutil / Disk Utility / fs_usage** — native tools extensively used in guides for disk health and I/O issues. apple-a-day already wraps `diskutil apfs list` for APFS container checks.
2. **Time Machine backup recency checks** — OSX-Monitoring-Tools has scripts that check Time Machine backup currency. apple-a-day already checks local snapshot count; should add backup recency.
3. **smartctl (via smartmontools)** — open-source S.M.A.R.T. diagnostics for SSD/HDD health. Common in Mac health guides. Requires `brew install smartmontools`. Can read SSD wear level, reallocated sectors, temperature.

smartctl is the biggest gap in our current v0.1 — we check APFS containers but not the physical drive health underneath.

## Supporting Evidence

> **Evidence: [HIGH]** — https://setapp.com/how-to/run-diagnostics-on-mac, https://github.com/jedda/OSX-Monitoring-Tools, retrieved 2026-03-22

## Caveats

None identified yet.
