---
id: "GOAL-002"
type: "goal"
title: "MCP server: Claude sessions can query Mac health"
status: "locked"
date: "2026-03-22"
depends_on: []
unlocks: []
---

Thin MCP wrapper over the diagnostic library (per ADR-001). Expose each check as an MCP tool: `mac_checkup`, `mac_crash_loops`, `mac_kernel_panics`, etc. Returns structured Finding objects. This is one of three surfaces (import, CLI, MCP), not the primary interface.
