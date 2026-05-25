---
id: TASK-0008
title: Network check module
status: Done
created: '2026-03-22'
priority: high
milestone: MS-0002
tags:
  - new-check
  - research-0005
definition-of-done:
  - 'check_network() returns findings for throughput, latency, Wi-Fi signal'
  - 'poor signal = WARNING, very poor = CRITICAL'
  - registered in ALL_CHECKS
visionlog_goal_id: GOAL-009
updated: '2026-03-22'
---
New check module: networkQuality (throughput/latency), airport command (Wi-Fi signal/noise/channel). From landscape research finding 0005.

**Completion notes:** Network module: Wi-Fi signal via system_profiler SPAirPortDataType (replaced deprecated airport command). SSID, RSSI, noise, SNR, channel, PHY mode. Speed test via networkQuality -s -c (JSON output). Throughput + responsiveness with Apple's RPM scale. 21 tests pass.
