---
id: TASK-0034
title: Replace system_profiler XProtect check with direct plist read (BRUTAL-006)
status: Done
created: '2026-04-02'
priority: high
milestone: MS-0003
tags:
  - brutal-forge
  - performance
updated: '2026-04-02'
---
system_profiler SPInstallHistoryDataType takes 10-15s. Read XProtect version directly from /Library/Apple/System/Library/CoreServices/XProtect.bundle/Contents/version.plist.
