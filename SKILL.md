# apple-a-day

Mac health diagnostic library for agents. Structured findings about system health — point-in-time checks and continuous vitals monitoring.

## Quick Use

```bash
# Full checkup — warnings and critical only
aad checkup --json --min-severity warning --fields severity,summary,fix

# Pre-task: is the machine healthy enough for heavy work?
aad checkup --json -c cpu_load -c thermal -c memory_pressure

# What happened while I was away? (shutdown causes, crash loops)
aad checkup --json -c shutdown_causes -c crash_loops -c kernel_panics

# Sample vitals right now (load, thermal, swap, top processes)
aad monitor --once --json

# Analyze vitals history — spikes, patterns, worst offenders
aad vitals --json --minutes 60
```

## Commands

| Command | What It Returns |
|---------|----------------|
| `aad checkup --json` | Full checkup — all 12 checks as JSON |
| `aad checkup --json --min-severity warning` | Only warnings and critical |
| `aad checkup --json --fields severity,summary,fix` | Limit fields (saves tokens) |
| `aad checkup --json -c cpu_load -c thermal` | Run specific checks only |
| `aad monitor --once --json` | Single vitals sample (load, thermal, swap, top CPU) |
| `aad monitor --interval 30` | Continuous sampling every 30s (foreground) |
| `aad vitals --json --minutes 60` | Analyze vitals history — spikes, offenders, trends |
| `aad score --json` | Health score matrix (0-100, 9 dimensions) |
| `aad trend --json` | Health trend — improving/degrading, recurring issues |
| `aad log --json -n 10` | Last 10 checkup results |
| `aad profile --json` | Mac user profile (hardware, dev tools, user type) |
| `aad schema` | JSON schema of all checks and output format |

## Available Checks (13)

| Check | What It Detects |
|-------|----------------|
| `crash_loops` | Processes crashing repeatedly (DiagnosticReports) |
| `kernel_panics` | Panic logs decoded into plain-english causes |
| `shutdown_causes` | Why the Mac shut down — thermal, panic, forced, clean |
| `cpu_load` | Load average vs core count, top resource hogs with categories |
| `thermal` | Thermal pressure, kernel_task throttling |
| `memory_pressure` | RAM pressure level and swap usage |
| `dylib_health` | Broken Homebrew dynamic library links |
| `disk_health` | APFS state, free space, Time Machine snapshot bloat |
| `launch_agents` | Crash-looping launchd services |
| `homebrew` | Outdated packages, brew doctor warnings |
| `security` | SIP, Gatekeeper, FileVault, XProtect freshness |
| `network` | Wi-Fi signal quality, throughput, responsiveness |
| `cleanup` | Stale apps (90+ days unused), orphaned launch agents, crash-looping services |

## Agent Patterns

**Pre-flight before heavy work:**
```bash
aad checkup --json -c cpu_load -c thermal -c memory_pressure --min-severity warning
# If empty findings array → green light
```

**Post-crash forensics:**
```bash
aad checkup --json -c shutdown_causes -c crash_loops -c kernel_panics
aad vitals --json --minutes 120
# Correlate shutdown cause with vitals spike timeline
```

**Continuous awareness (run as launchd daemon):**
```bash
aad monitor --interval 60
# Writes to ~/.config/eidos/aad-logs/vitals.ndjson
# Query anytime with: aad vitals --json
```

## Vitals Time-Series

`aad monitor` samples every N seconds to `~/.config/eidos/aad-logs/vitals.ndjson`. Each sample (~200 bytes):

```json
{"ts":"2026-03-22T23:45:15","load":[9.6,11.0,15.6],"cores":14,"top":[[60.9,"python3.12"],[43.5,"XprotectService"]],"thermal":0,"swap_mb":23335}
```

`aad vitals --json` analyzes the history and returns:
- Load spikes (start, end, peak, culprit processes)
- Thermal escalation timeline
- Swap trends
- Worst offenders ranked by frequency in top-CPU list

## Output Format

Each finding has:
- `severity`: ok, info, warning, critical
- `summary`: one-line plain-english description
- `details`: additional context (may be empty)
- `fix`: command or action to resolve (always present for warning/critical)

## Invariants

- All checks are **read-only** — nothing is modified
- No check requires **sudo** for basic operation
- Every warning/critical finding includes a **fix**
- `--json` output is always **valid JSON**
- Checks run in **parallel** by default
- **Zero runtime dependencies** — stdlib Python only
- Profile-aware — findings tailored to user type (developer, Docker user, AI agent user)
