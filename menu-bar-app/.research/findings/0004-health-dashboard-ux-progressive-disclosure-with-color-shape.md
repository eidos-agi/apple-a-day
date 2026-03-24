---
id: '0004'
title: 'Health dashboard UX: progressive disclosure with color + shape'
status: open
evidence: VERIFIED
sources: 1
created: '2026-03-24'
---

## Claim

Best practice for health dashboards: (1) Use 4-band color coding — green (#24a148), yellow, orange, red (#da1e28) — but NEVER rely on color alone (accessibility). Always pair color with a shape or icon (checkmark, warning triangle, X). (2) Carbon Design System rule: when consolidating multiple statuses, use the highest-attention color for the group. So if 6/7 health dimensions are green but 1 is red, the overall indicator is red. (3) Progressive disclosure: show aggregate health grade at top level (the menu bar icon), drill into dimension scores on click, drill into individual findings on expand. "Urgent info visible in under 2 seconds." (4) Health bands: Green (A-B), Yellow (C), Orange (D), Red (F). (5) Sparklines via DSFSparkline library — lightweight, SwiftUI-native, supports line/bar/dot graphs, macOS 10.13+. Perfect for vitals mini-graphs in the panel.

## Supporting Evidence

> **Evidence: [VERIFIED]** — carbondesignsystem.com/patterns/status-indicator-pattern, github.com/dagronf/DSFSparkline, koruux.com/50-examples-of-healthcare-UI, retrieved 2026-03-24

## Caveats

None identified yet.
