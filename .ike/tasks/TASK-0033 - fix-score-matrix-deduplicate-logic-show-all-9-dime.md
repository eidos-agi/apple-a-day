---
id: TASK-0033
title: 'Fix score matrix: deduplicate logic, show all 9 dimensions (BRUTAL-005)'
status: Done
created: '2026-04-02'
priority: high
milestone: MS-0003
tags:
  - brutal-forge
  - ux
updated: '2026-04-02'
---
Matrix computed in log.py and report.py independently. cli.py only shows 7 of 9 dimensions. Extract shared function, display all dimensions.
