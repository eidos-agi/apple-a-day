---
id: TASK-0016
title: Vitals sparklines (native SwiftUI Path, no external deps)
status: To Do
created: '2026-03-24'
priority: medium
tags:
  - macos-app
  - ux
  - visualization
dependencies:
  - TASK-0002
  - TASK-0004
acceptance-criteria:
  - 'Reusable SparklineView(data: [Double]) using SwiftUI Path'
  - Sparkline for CPU load (last 60 samples)
  - Sparkline for thermal (last 60 samples)
  - Sparkline for memory pressure (last 60 samples)
  - Color reflects current value severity
  - Graceful fallback if no vitals data exists
  - No external charting dependencies
visionlog_goal_id: GOAL-010
updated: '2026-03-24'
---
Add compact sparkline graphs for vitals time-series data in the panel. Use native SwiftUI Path/Shape API — create a reusable `SparklineView(data: [Double])` component. Show last ~60 samples (1 hour at 1/min) for CPU load, thermal, and memory pressure. Color the sparkline by current value (green→orange→red). Defer DSFSparkline or other charting libraries to v2 when interactive scrubbing may be needed.
