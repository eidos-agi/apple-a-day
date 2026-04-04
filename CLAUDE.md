# apple-a-day

Agent-native Mac health diagnostic toolkit. Zero dependencies. Read-only by default.

## What This Is

apple-a-day answers "what's wrong with this Mac?" in a single call. Every finding includes a severity, plain-english explanation, and actionable fix command. Designed for AI agents first, friendly to humans second.

## Architecture

```
apple_a_day/          Python library (the source of truth)
  checks/             13 independent health check modules
  runner.py           Parallel orchestrator (ThreadPoolExecutor)
  models.py           Finding, CheckResult, Severity, CheckError
  vitals.py           Time-series sampling → ~/.config/eidos/aad-logs/vitals.ndjson
  log.py              Checkup history → ~/.config/eidos/aad-logs/checkup.ndjson
  profile.py          Mac user profiling → ~/.config/eidos/mac-profile.json
  cli.py              `aad` CLI (argparse, zero deps)
  browser.py          Chrome extension native host management
  report.py           Filtering and formatting
  report_html.py      HTML report generation (Jinja2, optional dep)

browser/              Chrome extension (Manifest V3)
  background.js       Tab lifecycle events, snapshots, badge
  popup.html/js/css   Stats UI
  native-host/        Native messaging host → browser.ndjson

app/                  macOS menu bar app (SwiftUI)
  AppleADay/          Stethoscope icon, health grade, findings panel
```

## The 13 Checks

| Module | What |
|--------|------|
| crash_loops | Processes crashing repeatedly (DiagnosticReports) |
| kernel_panics | Decoded panic logs from last 7 days |
| shutdown_causes | Abnormal shutdown reasons |
| cpu_load | Load average vs core count, top hogs |
| thermal | Thermal pressure, kernel_task throttling |
| memory_pressure | RAM pressure level, swap usage |
| disk_health | APFS state, free space, snapshot bloat |
| dylib_health | Broken Homebrew dynamic library links |
| launch_agents | Crash-looping, orphaned, stuck launchd services |
| homebrew | Outdated packages, doctor warnings |
| security | SIP, Gatekeeper, FileVault, XProtect |
| network | Wi-Fi signal, speed test, responsiveness |
| cleanup | Stale apps, orphaned agents, crash-loopers |

## Check Module Contract

Every check follows the same pattern:

```python
def check_example() -> CheckResult:
    result = CheckResult(name="Example")
    # ... gather data using subprocess + stdlib only ...
    result.findings.append(Finding(
        check="example",
        severity=Severity.WARNING,
        summary="One-line plain english",
        details="Additional context",
        fix="command to fix it"
    ))
    return result
```

Register in `checks/__init__.py` → `ALL_CHECKS`. The runner handles parallelism.

## Data Locations

| File | What |
|------|------|
| `~/.config/eidos/aad-logs/vitals.ndjson` | Time-series system samples (CPU, thermal, swap) |
| `~/.config/eidos/aad-logs/checkup.ndjson` | Checkup history with scores and grades |
| `~/.config/eidos/aad-logs/browser.ndjson` | Chrome tab events and snapshots |
| `~/.config/eidos/mac-profile.json` | User profile (hardware, tools, user type) |

All NDJSON. All rotate at size limits (5-10 MB). Machine-first, human-readable second.

## Ecosystem

| Repo | Role |
|------|------|
| **apple-a-day** (this) | Health diagnostics — what's wrong |
| **space-hog** | Disk cleanup — what to remove |

Shared integration point: `~/.config/eidos/mac-profile.json` (apple-a-day creates it, space-hog reads it). Future: space-hog as an apple-a-day plugin.

## CLI Quick Reference

```bash
aad checkup                    # Run all checks
aad checkup --json             # Agent-friendly JSON
aad checkup -c cleanup         # Single check
aad monitor --once             # One vitals sample
aad vitals --minutes 60        # Analyze recent vitals
aad score                      # Health grade (A-F)
aad browser install            # Install Chrome native host
aad browser status             # Check native host state
aad schema                     # JSON schema for agents
aad profile                    # Mac user profile
```

## Hard Rules

- **Zero runtime dependencies** — stdlib + macOS native tools only. Optional extras (rich, jinja2) are opt-in.
- **Read-only by default** — Checks never modify the system. Fixes are suggested, not applied.
- **Mac-only** — Uses macOS-specific APIs and tools. No cross-platform.
- **Plain english** — Every finding readable by a non-technical human.
- **Files under 2700 lines** — Break up anything larger.
- **Soft deletes only** — When managing data, use timestamps not hard deletes.
