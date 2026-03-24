"""Detect services crash-looping via DiagnosticReports."""

from collections import Counter
from datetime import datetime
from pathlib import Path

from ..models import CheckResult, Finding, Severity

REPORT_DIRS = [
    Path.home() / "Library/Logs/DiagnosticReports",
    Path("/Library/Logs/DiagnosticReports"),
]

CRASH_EXTENSIONS = {".ips", ".crash"}


def check_crash_loops(hours: int = 24) -> CheckResult:
    """Find processes that have crashed repeatedly in the last N hours."""
    result = CheckResult(name="Crash Loops")
    cutoff = datetime.now().timestamp() - (hours * 3600)
    crash_counts: Counter[str] = Counter()

    for report_dir in REPORT_DIRS:
        if not report_dir.exists():
            continue
        for f in report_dir.iterdir():
            if f.suffix not in CRASH_EXTENSIONS:
                continue
            if f.stat().st_mtime < cutoff:
                continue
            # Filename format: ProcessName-YYYY-MM-DD-HHMMSS.ips
            process_name = f.stem.rsplit("-", 4)[0] if f.stem.count("-") >= 4 else f.stem
            crash_counts[process_name] += 1

    for process, count in crash_counts.most_common():
        if count >= 10:
            severity = Severity.CRITICAL
        elif count >= 3:
            severity = Severity.WARNING
        else:
            severity = Severity.INFO

        result.findings.append(
            Finding(
                check="crash_loops",
                severity=severity,
                summary=f"{process} crashed {count} times in the last {hours}h",
                details="Crash reports found in DiagnosticReports directories.",
                fix=f"Check: `log show --predicate 'process == \"{process}\"' --last {hours}h`"
                f" or reinstall the service.",
            )
        )

    if not result.findings:
        result.findings.append(
            Finding(
                check="crash_loops",
                severity=Severity.OK,
                summary=f"No crash loops detected in the last {hours}h",
            )
        )

    return result
