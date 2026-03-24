"""Parse kernel panic reports and surface plain-english causes."""

import json
from datetime import datetime
from pathlib import Path

from ..models import CheckResult, Finding, Severity

PANIC_DIR = Path("/Library/Logs/DiagnosticReports")

KNOWN_PANIC_PATTERNS = {
    "watchdog timeout": "System froze — a core process couldn't check in. Usually caused by a hung driver or runaway service.",
    "hibernate_is_resume": "Mac panicked while going to sleep or waking up. Hibernate image was corrupted.",
    "iBoot panic": "Low-level boot firmware panic — often a failed hibernate resume.",
    "kernel memory": "Kernel ran out of memory. Check for memory-hungry processes.",
    "zone map exhaustion": "Kernel zone allocator exhausted. Too many open files or network connections.",
}


def check_kernel_panics(days: int = 7) -> CheckResult:
    """Find and interpret kernel panics from the last N days."""
    result = CheckResult(name="Kernel Panics")

    if not PANIC_DIR.exists():
        result.findings.append(
            Finding(
                check="kernel_panics",
                severity=Severity.OK,
                summary="No panic report directory found",
            )
        )
        return result

    cutoff = datetime.now().timestamp() - (days * 86400)
    panic_files = sorted(
        [f for f in PANIC_DIR.glob("panic-*.panic") if f.stat().st_mtime >= cutoff],
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )

    if not panic_files:
        result.findings.append(
            Finding(
                check="kernel_panics",
                severity=Severity.OK,
                summary=f"No kernel panics in the last {days} days",
            )
        )
        return result

    for pf in panic_files:
        try:
            raw = pf.read_text()
            # Panic files may have a JSON header line + JSON body
            lines = raw.split("\n", 1)
            if len(lines) > 1:
                body = json.loads(lines[1])
            else:
                body = json.loads(lines[0])

            panic_string = body.get("panicString", "")
            date = body.get("date", "unknown")

            # Match known patterns
            explanation = "Unknown panic type — review the full report."
            for pattern, desc in KNOWN_PANIC_PATTERNS.items():
                if pattern.lower() in panic_string.lower():
                    explanation = desc
                    break

            result.findings.append(
                Finding(
                    check="kernel_panics",
                    severity=Severity.CRITICAL,
                    summary=f"Kernel panic on {date}",
                    details=explanation,
                    fix=f"Full report: {pf}",
                )
            )
        except (json.JSONDecodeError, KeyError):
            result.findings.append(
                Finding(
                    check="kernel_panics",
                    severity=Severity.WARNING,
                    summary=f"Unparseable panic report: {pf.name}",
                    fix=f"Manually review: {pf}",
                )
            )

    return result
