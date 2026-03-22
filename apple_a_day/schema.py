"""Runtime schema introspection for agent discoverability."""

from . import __version__
from .checks import ALL_CHECKS


def get_schema() -> dict:
    """Return JSON-serializable schema describing all checks and output format."""
    checks = []
    for fn in ALL_CHECKS:
        checks.append({
            "name": fn.__name__.replace("check_", ""),
            "function": fn.__name__,
            "description": (fn.__doc__ or "").strip().split("\n")[0],
        })

    return {
        "tool": "apple-a-day",
        "version": __version__,
        "description": "Mac health diagnostic library. Returns structured findings about system health.",
        "usage": {
            "python": "from apple_a_day.runner import run_all_checks; report = run_all_checks()",
            "cli": "aad checkup --json",
            "cli_filtered": "aad checkup --json --min-severity warning --fields severity,summary,fix",
        },
        "checks": checks,
        "output_schema": {
            "finding": {
                "check": "string — which check module produced this finding",
                "severity": "enum: ok | info | warning | critical",
                "summary": "string — plain-english one-line description",
                "details": "string — additional context (may be empty)",
                "fix": "string — concrete command or action to resolve (may be empty for ok/info)",
            },
            "report": {
                "mac": "object — host identification (os_version, arch, cpu, memory_gb, hostname)",
                "duration_ms": "int — total check execution time in milliseconds",
                "findings": "array of finding objects",
            },
        },
        "invariants": [
            "All checks are read-only — no system state is ever modified",
            "No check requires sudo for basic operation",
            "Every critical/warning finding includes a non-empty fix field",
            "Output with --json is always valid JSON",
            "Checks run in parallel by default; use --no-parallel for sequential",
        ],
    }
