---
id: '0001'
title: OSS system monitors worth studying
status: open
evidence: MODERATE
sources: 1
created: '2026-03-22'
---

## Claim

Four open-source projects provide reusable patterns or code for Mac system monitoring:

1. **Stats** — macOS menu-bar monitor (CPU, GPU, memory, disks, network, sensors). Swift, very popular. Good reference for how to read Apple Silicon sensor data via IOKit/SMC.
2. **Mac Monitor** — advanced event/telemetry monitor using Endpoint Security & system extensions. Relevant for security telemetry and process triage.
3. **macOS-Monitoring (MacStadium)** — shell/awk scripts built around native macOS commands for simple host health monitoring. Good template for "native command wrappers."
4. **OSX-Monitoring-Tools (jedda)** — Nagios-oriented checks for SMC sensors, memory, backups, launchd status, certificates. Broad coverage of hardware sensors, backups, directory services. Good source of checks to port/modernize.

Stats is the richest codebase to learn from for sensor/thermal data. OSX-Monitoring-Tools has the broadest check coverage. macOS-Monitoring has the simplest patterns (shell wrappers) closest to our approach.

## Supporting Evidence

> **Evidence: [MODERATE]** — https://github.com/exelban/stats, https://github.com/Brandon7CC/mac-monitor, https://github.com/macstadium/macOS-Monitoring, https://github.com/jedda/OSX-Monitoring-Tools, retrieved 2026-03-22

## Caveats

None identified yet.
