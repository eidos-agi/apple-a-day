---
id: TASK-0036
title: 'Clean up dead code: ensemble_similarity.py, replacement_detection.py, disk_health.py:103'
status: Done
created: '2026-04-02'
priority: medium
milestone: MS-0003
tags:
  - brutal-forge
  - cleanup
updated: '2026-04-02'
---
Three files with dead code: ensemble_similarity.py never imported as scorer, replacement_detection.py never imported at all, disk_health.py has discarded list comprehension. Wire in or delete.

Removed replacement_detection.py (truly dead). ensemble_similarity.py is used by report_html.py — kept. Removed dead list comprehension in disk_health.py:103.
