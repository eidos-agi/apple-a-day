"""Check resource-sentinel: the always-on Go guardian that defends disk/RAM/CPU.

apple-a-day is read-only; it never mutates the machine. resource-sentinel is the
mutating enforcer (safe-cleans caches, truncates oversized logs, SIGSTOPs runaway
writers). This check makes aad the single pane of glass over that enforcer by
reading its localhost status API — so the two daemons stop drifting apart and a
dead guardian gets surfaced in the daily checkup.

Deliberately does NOT re-report free-GB severity — that stays check_disk_health's
job. This reports the *guardian's* state: alive, what it paused, what it cleaned.

Stdlib only.
"""

import json
import urllib.request
import urllib.error

from ..models import CheckResult, Finding, Severity

STATUS_URL = "http://127.0.0.1:9341/status"
RESTART = "launchctl kickstart -k gui/$(id -u)/com.eidos.resource-sentinel"


def _classify(status: dict) -> Finding:
    """Turn a /status payload into one Finding. Pure — unit-testable offline."""
    free_gb = status.get("free_gb")
    paused = status.get("paused_pids") or []
    alerts = status.get("recent_alerts") or []

    if paused:
        return Finding(
            check="resource_sentinel",
            severity=Severity.WARNING,
            summary=f"Guardian SIGSTOP'd {len(paused)} process(es) — awaiting your call",
            details="Paused (kill -STOP) writers: " + ", ".join(paused),
            fix="Resume with `kill -CONT <pid>` once you've dealt with the disk pressure, "
            "or let the growth subside. See `sentinel` CLI / :9341/logs.",
        )
    if alerts:
        return Finding(
            check="resource_sentinel",
            severity=Severity.INFO,
            summary=f"Guardian healthy, acted recently ({free_gb} GB free)",
            details="Latest: " + alerts[-1],
            fix="",
        )
    return Finding(
        check="resource_sentinel",
        severity=Severity.OK,
        summary=f"Guardian healthy, quiet ({free_gb} GB free)",
    )


def check_resource_sentinel() -> CheckResult:
    """Read resource-sentinel's :9341/status and surface the guardian's state."""
    result = CheckResult(name="Resource Sentinel")
    try:
        with urllib.request.urlopen(STATUS_URL, timeout=3) as resp:
            status = json.load(resp)
    except (urllib.error.URLError, OSError, TimeoutError, ValueError):
        # Unreachable == the guard that keeps the boot disk off zero isn't running.
        result.findings.append(
            Finding(
                check="resource_sentinel",
                severity=Severity.CRITICAL,
                summary="GUARDIAN DOWN — resource-sentinel not responding on :9341",
                details="The always-on disk/RAM/CPU guardian is unreachable. Nothing is "
                "safe-cleaning caches or naming runaway writers.",
                fix=f"Restart it: `{RESTART}` (binary at ~/.local/bin/resource-sentinel).",
            )
        )
        return result

    result.findings.append(_classify(status))
    return result
