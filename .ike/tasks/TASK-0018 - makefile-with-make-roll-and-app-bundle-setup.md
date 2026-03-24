---
id: TASK-0018
title: Makefile with `make roll` and app bundle setup
status: Done
created: '2026-03-24'
priority: high
tags:
  - macos-app
  - devops
dependencies:
  - TASK-0001
acceptance-criteria:
  - '`make roll` kills, builds, copies, codesigns, registers, relaunches'
  - App bundle at /Applications/AppleADay.app with correct structure
  - Info.plist included in bundle with LSUIElement=true
  - lsregister called so icon appears immediately
  - '`make install-cli` runs pip install -e .'
visionlog_goal_id: GOAL-010
updated: '2026-03-24'
---
Create Makefile at repo root with `make roll` target following ManyHats pattern: pkill, swift build, copy binary to /Applications/AppleADay.app/Contents/MacOS/, codesign, lsregister, sleep 1, open. Also create the .app bundle structure with Info.plist. Add `make install-cli` for `pip install -e .` convenience.

Makefile at repo root with `make roll` (pkill, swift build, copy, codesign, lsregister, open), `make install-cli`, `make test`. App bundle at /Applications/AppleADay.app with Info.plist (LSUIElement=true).
