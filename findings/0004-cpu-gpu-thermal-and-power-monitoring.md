---
id: '0004'
title: 'CPU, GPU, thermal, and power monitoring'
status: open
evidence: MODERATE
sources: 1
created: '2026-03-22'
---

## Claim

Key tools for thermal/power monitoring:

1. **powermetrics** — Apple's native tool for thermal/power/CPU state. Requires sudo. Surfaces CPU/GPU frequency, package power, thermal pressure, fan speed. This is the gold standard for Apple Silicon monitoring.
2. **memory_pressure / vm_stat** — native tools for memory pressure and paging stats. apple-a-day already uses these.
3. **Stats (exelban)** — its Swift codebase shows how to read SMC sensor data via IOKit for temperature, fan speed, and power draw without sudo. This is the pattern to study for GOAL-004 (thermal monitoring).
4. **Novabench** — free tier CPU/GPU benchmarking. Not OSS but widely referenced. Not something we'd integrate, but useful as a comparison point.

For GOAL-004, the path is: use `powermetrics` when sudo is available, fall back to IOKit/SMC direct reads (Stats pattern) when not.

## Supporting Evidence

> **Evidence: [MODERATE]** — https://support.kandji.io/kb/how-to-generate-a-sysdiagnose-in-macos, https://github.com/exelban/stats, https://www.avast.com/c-how-to-test-mac-performance, retrieved 2026-03-22

## Caveats

None identified yet.
