---
id: "GOAL-007"
type: "goal"
title: "Zero-dep rewrite: drop click/rich, argparse + ANSI"
status: "available"
date: "2026-03-22"
depends_on: []
unlocks: []
---

Per ADR-002: replace click with argparse, replace rich with ANSI escape codes + Unicode box-drawing. Move rich to optional dependency under `[rich]` extra. Core runs on stdlib Python only.
