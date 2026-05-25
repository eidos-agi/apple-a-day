---
id: "GOAL-010"
type: "goal"
title: "macOS menu bar app — daemon visibility and quick health actions"
status: "available"
date: "2026-03-24"
depends_on: []
unlocks: []
---

## Why

apple-a-day runs two launchd daemons (daily checkup + vitals monitor) but has zero visual presence. A daemon without an icon is invisible work — the user has no idea it's running, healthy, or stuck.

## What

A lightweight SwiftUI MenuBarExtra app that:
- Shows a **stethoscope icon** (SF Symbol) in the menu bar, color-coded by health grade (green/yellow/orange/red)
- On click, shows a panel with: overall health grade, 7 dimension scores, active findings (warnings/criticals), vitals sparklines, daemon status, last checkup timestamp
- Quick actions: run checkup now, open HTML report, view score matrix, toggle vitals daemon
- Architecture: thin observer app that reads daemon output from `~/.config/eidos/aad-logs/` and shells out to `aad` CLI — does NOT run checks itself

## Design Principles (from research)
- **Progressive disclosure**: icon → grade → dimensions → findings
- **Color + shape**: never rely on color alone (accessibility). Pair with grade letter (A-F) and status icons
- **Consolidation rule**: overall color = worst dimension color (Carbon Design System pattern)
- **Sparklines**: DSFSparkline library for compact vitals visualization
- **ManyHats pattern**: MenuBarExtra(.window), inline views (no .sheet()), LSUIElement=true, `make roll` deploy

## Research
See `.research/menu-bar-app/` — 4 verified findings covering UX patterns, SF Symbols, architecture, and health dashboard design.
