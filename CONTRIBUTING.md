# Contributing to apple-a-day

Thanks for your interest in making Macs healthier.

## Quick start

```bash
git clone https://github.com/eidos-agi/apple-a-day.git
cd apple-a-day
pip install -e ".[dev]"
aad checkup  # verify it works
```

## Adding a new check module

Each check lives in `apple_a_day/checks/` as its own file. Here's the pattern:

```python
# apple_a_day/checks/your_check.py

from ..models import CheckResult, Finding, Severity

def check_your_thing() -> CheckResult:
    result = CheckResult(name="Your Check")

    # Do your diagnostics using native macOS tools
    # ...

    result.findings.append(Finding(
        check="your_check",
        severity=Severity.WARNING,
        summary="Plain english: what's wrong",
        details="More context if needed",
        fix="The exact command or step to fix it",
    ))

    return result
```

Then register it in `apple_a_day/checks/__init__.py`.

## Rules

1. **Mac-only.** No `platform.system()` checks. No Linux/Windows support. Use macOS-native tools directly (`otool`, `diskutil`, `launchctl`, etc.).

2. **Read-only.** Check modules must never modify system state. No killing processes, no writing files, no running `brew install`. Checks observe; fixes are a separate concern.

3. **Plain english, always.** Every finding needs:
   - A `summary` a non-technical person could understand
   - A `fix` with a concrete next step (command, setting, or action)
   - Never surface raw error codes without explanation

4. **Graceful failure.** If a check can't run (missing tool, permission denied, unexpected output), return an INFO finding explaining why — don't crash.

5. **No heavy dependencies.** We use `click` and `rich` for the CLI. Check modules should use `subprocess` to call native tools. Avoid pulling in large libraries.

## Severity guidelines

| Severity | When to use |
|----------|------------|
| `CRITICAL` | Active harm: crash loops, kernel panics, nearly full disk, broken services |
| `WARNING` | Degraded state: high swap, outdated security, many stale packages |
| `INFO` | Worth noting but not urgent: one-off crash, minor config issue |
| `OK` | Check passed — everything looks good |

## Running tests

```bash
pytest
```

## Code style

We use ruff for linting:

```bash
ruff check .
ruff format .
```

## Pull requests

- One check module per PR (unless they're closely related)
- Include example output showing what your check finds
- Test on your own Mac first — we don't have CI for macOS yet
- Keep PRs focused. Bug fixes and features are separate PRs.

## Reporting issues

Found something apple-a-day should catch but doesn't? Open an issue with:

1. What happened on your Mac
2. How you diagnosed it manually
3. What apple-a-day should have told you

These real-world cases are the most valuable contributions.
