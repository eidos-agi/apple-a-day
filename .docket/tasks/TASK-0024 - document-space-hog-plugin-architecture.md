---
id: TASK-0024
title: Document space-hog plugin architecture
status: Done
created: '2026-04-02'
priority: high
milestone: MS-0003
tags:
  - architecture
  - space-hog
---
Design and document how space-hog becomes a plugin of apple-a-day. Shared profile, check result translation, CLI integration (aad checkup runs space-hog findings), optional dependency model.

**Done 2026-07-20 (Go rewrite):** space-hog gained a `--json` emitter (`space_hog/json_output.py`) reusing its own scanners. aad's Go `Space Hogs` check (`internal/aad/check_space_hogs.go`, opt-in) runs `space-hog --json` and translates its sections into findings — aad stays read-only, space-hog does the scanning (same pattern as the resource-sentinel plugin). Optional-dependency model: check emits an INFO "not installed" finding if `space-hog` isn't on PATH. Also sped up space-hog's `get_dir_size` (Python rglob → `du -sk`) and scoped the home-wide hog-walk out of the default JSON scan (kept for explicit paths) so the plugin scan runs in ~100s instead of timing out. Verified end-to-end: surfaced 185.9 GB reclaimable (Docker 44 GB, Claude Code cache 29 GB, Ollama 16 GB, …).
