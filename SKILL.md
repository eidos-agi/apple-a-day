# apple-a-day

Mac health diagnostic library. Returns structured findings about system health.

## What This Tool Does

Runs 7 diagnostic checks against macOS native tools and returns findings with severity, plain-english summary, and fix command for each issue found.

## Quick Use

```python
from apple_a_day.runner import run_all_checks
report = run_all_checks()
for r in report.results:
    for f in r.findings:
        if f.severity.value == "critical":
            print(f.summary, "→", f.fix)
```

Or via CLI:

```
aad checkup --json --min-severity warning
```

## Commands

| Command | What It Returns |
|---------|----------------|
| `aad checkup --json` | Full checkup as JSON |
| `aad checkup --json --min-severity warning` | Only warnings and critical |
| `aad checkup --json --fields severity,summary,fix` | Limit fields (saves tokens) |
| `aad checkup --json -c crash_loops -c kernel_panics` | Run specific checks only |
| `aad schema` | JSON schema of all checks and output format |

## Available Checks

| Check | What It Detects |
|-------|----------------|
| `crash_loops` | Processes crashing repeatedly (DiagnosticReports) |
| `kernel_panics` | Panic logs decoded into causes |
| `dylib_health` | Broken dynamic library links |
| `memory_pressure` | RAM pressure and swap usage |
| `disk_health` | APFS state, free space, snapshot bloat |
| `launch_agents` | Crash-looping launchd services |
| `homebrew` | Outdated packages, doctor warnings |

## Output Format

Each finding has:
- `severity`: ok, info, warning, critical
- `summary`: one-line plain-english description
- `details`: additional context (may be empty)
- `fix`: command or action to resolve (always present for warning/critical)

## Invariants

- All checks are **read-only** — nothing is modified on the system
- No check requires **sudo** for basic operation
- Every warning/critical finding includes a **fix**
- `--json` output is always **valid JSON**
- Checks run in **parallel** by default
- **Zero runtime dependencies** — stdlib Python only
