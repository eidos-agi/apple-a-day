---
id: TASK-0012
title: Scaffold SwiftUI menu bar app (Package.swift, Info.plist, ManyHats pattern)
status: Done
created: '2026-03-24'
priority: high
tags:
  - macos-app
  - scaffold
acceptance-criteria:
  - Package.swift with SwiftUI dependency compiles via `swift build`
  - Info.plist with LSUIElement=true and CFBundleName
  - App struct uses MenuBarExtra(.window) with stethoscope SF Symbol
  - App launches and shows stethoscope icon in menu bar
  - Empty panel appears on click
visionlog_goal_id: GOAL-010
updated: '2026-03-24'
assignees:
  - '@claude'
---
Create the app skeleton at `app/AppleADay/` following the ManyHats pattern. Swift Package Manager project with SwiftUI MenuBarExtra(.window), LSUIElement=true in Info.plist, basic App struct with stethoscope SF Symbol icon. Should compile and show the icon in the menu bar with an empty panel.

Scaffolded at app/AppleADay/. Package.swift compiles clean. MenuBarExtra with stethoscope SF Symbol. Models for all aad JSON output formats (ScoreOutput, CheckupLogEntry, VitalsSample). AppState enum for CLI-not-found, no-data, ready, error states.
