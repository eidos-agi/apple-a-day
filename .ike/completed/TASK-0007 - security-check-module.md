---
id: TASK-0007
title: Security check module
status: Done
created: '2026-03-22'
priority: high
milestone: MS-0002
tags:
  - new-check
  - research-0006
definition-of-done:
  - 'check_security() returns findings for SIP, Gatekeeper, XProtect, FileVault'
  - SIP disabled = CRITICAL finding
  - FileVault off = WARNING finding
  - registered in ALL_CHECKS
visionlog_goal_id: GOAL-008
updated: '2026-03-22'
---
New check module: csrutil (SIP status), spctl (Gatekeeper), XProtect definition freshness, FileVault encryption status. From landscape research finding 0006.

**Completion notes:** Security module: SIP (csrutil), Gatekeeper (spctl), FileVault (fdesetup), XProtect freshness (system_profiler install history). All four green on test Mac.
