"""Structured logging for apple-a-day.

Every checkup writes a log entry to ~/.config/eidos/aad-logs/
in newline-delimited JSON (NDJSON). One line per checkup run.

Agents read these logs to understand Mac health trends over time
without re-running checks. Format is machine-first, human-readable second.
"""

import json
from datetime import datetime
from pathlib import Path


LOG_DIR = Path.home() / ".config" / "eidos" / "aad-logs"
CURRENT_LOG = LOG_DIR / "checkup.ndjson"
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10 MB, then rotate


def _rotate_if_needed():
    """Rotate log if it exceeds max size."""
    if CURRENT_LOG.exists() and CURRENT_LOG.stat().st_size > MAX_LOG_SIZE:
        rotated = LOG_DIR / f"checkup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.ndjson"
        CURRENT_LOG.rename(rotated)


def _detect_trigger() -> str:
    """Detect what triggered this checkup: boot, daily, or manual."""
    import subprocess
    try:
        out = subprocess.run(
            ["sysctl", "-n", "kern.boottime"],
            capture_output=True, text=True, timeout=5,
        )
        # kern.boottime format: "{ sec = 1711108800, usec = 0 } ..."
        boot_sec = int(out.stdout.split("sec = ")[1].split(",")[0])
        uptime_seconds = int(datetime.now().timestamp()) - boot_sec
        if uptime_seconds < 300:  # less than 5 minutes since boot
            return "boot"
    except (subprocess.TimeoutExpired, OSError, ValueError, IndexError):
        pass
    return "scheduled"


def log_checkup(report, trigger: str | None = None) -> Path:
    """Write a checkup result as one NDJSON line.

    Format per line:
    {
        "ts": "2026-03-22T10:40:38",
        "duration_ms": 25000,
        "mac": { "os_version": "15.3.1", "cpu": "Apple M4 Max", ... },
        "counts": { "critical": 3, "warning": 5, "ok": 12, "info": 4 },
        "criticals": [ "watchman crashed 217 times", "Kernel panic on ..." ],
        "warnings": [ "Swap usage: 27798M", "Boot disk 89% full" ]
    }

    Agents can: tail -1 for latest, jq for trends, grep for specific issues.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    _rotate_if_needed()

    counts = {"critical": 0, "warning": 0, "info": 0, "ok": 0}
    criticals = []
    warnings = []

    for r in report.results:
        for f in r.findings:
            sev = f.severity.value
            counts[sev] = counts.get(sev, 0) + 1
            if sev == "critical":
                criticals.append(f.summary)
            elif sev == "warning":
                warnings.append(f.summary)

    # Score matrix: 7 dimensions, each 0-100
    # Maps check names → dimensions (some checks contribute to multiple)
    dimension_checks = {
        "stability": ["Crash Loops", "Kernel Panics", "Shutdown Causes"],
        "memory": ["Memory Pressure"],
        "storage": ["Disk Health"],
        "services": ["Launch Agents"],
        "security": ["Security"],
        "infra": ["Dynamic Library Health", "Homebrew"],
        "network": ["Network"],
        "cpu": ["CPU Load"],
        "thermal": ["Thermal"],
    }

    # Score each check: 0 (critical found), 50 (warning), 80 (info only), 100 (all ok)
    check_scores = {}
    for r in report.results:
        score = 100
        for f in r.findings:
            s = f.severity.value
            if s == "critical":
                score = min(score, 0)
            elif s == "warning":
                score = min(score, 50)
            elif s == "info":
                score = min(score, 80)
        check_scores[r.name] = score

    # Roll up to dimensions (worst score of contributing checks)
    matrix = {}
    for dim, checks in dimension_checks.items():
        scores = [check_scores.get(c, 100) for c in checks]
        matrix[dim] = min(scores) if scores else 100

    # Overall: weighted — stability and memory matter more than network
    weights = {
        "stability": 3,
        "cpu": 3,
        "memory": 2,
        "thermal": 2,
        "storage": 2,
        "services": 2,
        "security": 1,
        "infra": 1,
        "network": 1,
    }
    weighted_sum = sum(matrix.get(d, 100) * w for d, w in weights.items())
    total_weight = sum(weights.values())
    overall = round(weighted_sum / total_weight)

    if overall >= 90:
        grade = "A"
    elif overall >= 75:
        grade = "B"
    elif overall >= 50:
        grade = "C"
    elif overall >= 25:
        grade = "D"
    else:
        grade = "F"

    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "trigger": trigger or _detect_trigger(),
        "duration_ms": report.duration_ms,
        "mac": report.mac_info,
        "score": overall,
        "grade": grade,
        "matrix": matrix,
        "counts": counts,
        "criticals": criticals,
        "warnings": warnings,
    }

    with open(CURRENT_LOG, "a") as f:
        f.write(json.dumps(entry, separators=(",", ":")) + "\n")

    return CURRENT_LOG


def read_recent(n: int = 10) -> list[dict]:
    """Read the last N checkup log entries."""
    if not CURRENT_LOG.exists():
        return []

    lines = CURRENT_LOG.read_text().strip().split("\n")
    entries = []
    for line in lines[-n:]:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def trend_summary() -> dict | None:
    """Summarize health trend from logs.

    Returns:
    {
        "entries": 42,
        "first": "2026-03-22",
        "last": "2026-03-22",
        "avg_criticals": 3.2,
        "avg_warnings": 5.1,
        "improving": true,  # fewer issues in recent entries vs older
        "recurring": ["watchman crashed", "Swap usage"]  # issues appearing >50% of entries
    }
    """
    entries = read_recent(100)
    if len(entries) < 2:
        return None

    # Recurring issues
    issue_counts = {}
    for e in entries:
        for c in e.get("criticals", []) + e.get("warnings", []):
            # Normalize: strip numbers and dates for grouping
            key = c.split(" crashed ")[0] if " crashed " in c else c.split(" on ")[0] if " on " in c else c[:50]
            issue_counts[key] = issue_counts.get(key, 0) + 1

    threshold = len(entries) * 0.5
    recurring = [k for k, v in issue_counts.items() if v >= threshold]

    # Trend: compare first half vs second half
    mid = len(entries) // 2
    first_half_avg = sum(e["counts"].get("critical", 0) for e in entries[:mid]) / max(mid, 1)
    second_half_avg = sum(e["counts"].get("critical", 0) for e in entries[mid:]) / max(len(entries) - mid, 1)

    return {
        "entries": len(entries),
        "first": entries[0].get("ts", "")[:10],
        "last": entries[-1].get("ts", "")[:10],
        "avg_criticals": round(sum(e["counts"].get("critical", 0) for e in entries) / len(entries), 1),
        "avg_warnings": round(sum(e["counts"].get("warning", 0) for e in entries) / len(entries), 1),
        "improving": second_half_avg < first_half_avg,
        "recurring": recurring,
    }
