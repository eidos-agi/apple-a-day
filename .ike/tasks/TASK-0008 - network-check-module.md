---
id: TASK-0008
title: Network check module
status: To Do
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
---
New check module: networkQuality (throughput/latency), airport command (Wi-Fi signal/noise/channel). From landscape research finding 0005.
