"""Audit launchd agents for rogue, crashed, or high-restart services."""

import plistlib
import subprocess
from pathlib import Path

from ..context import get_context, crash_loop_fix
from ..models import CheckResult, Finding, Severity

AGENT_DIRS = [
    Path.home() / "Library/LaunchAgents",
    Path("/Library/LaunchAgents"),
    Path("/Library/LaunchDaemons"),
]


def check_launch_agents() -> CheckResult:
    """Find launchd services that are crashing, unknown, or misconfigured."""
    result = CheckResult(name="Launch Agents")
    ctx = get_context()

    # Get list of services and their status
    try:
        out = subprocess.run(
            ["launchctl", "list"],
            capture_output=True, text=True, timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError):
        result.findings.append(Finding(
            check="launch_agents",
            severity=Severity.INFO,
            summary="Could not query launchctl",
        ))
        return result

    # Parse launchctl output: PID Status Label
    crashed_services = []
    for line in out.stdout.strip().split("\n")[1:]:  # skip header
        parts = line.split("\t")
        if len(parts) >= 3:
            pid, status, label = parts[0], parts[1], parts[2]
            # Non-zero exit status = crashed or errored
            try:
                status_code = int(status)
                if status_code != 0 and pid == "-":
                    crashed_services.append((label, status_code))
            except ValueError:
                continue

    # Also scan plist files for KeepAlive services (crash loop risk)
    keepalive_services = []
    for agent_dir in AGENT_DIRS:
        if not agent_dir.exists():
            continue
        for plist_file in agent_dir.glob("*.plist"):
            try:
                with open(plist_file, "rb") as f:
                    plist = plistlib.load(f)
                label = plist.get("Label", plist_file.stem)
                keep_alive = plist.get("KeepAlive", False)
                if keep_alive and keep_alive is not False:
                    keepalive_services.append((label, plist_file))
            except (plistlib.InvalidFileException, OSError):
                continue

    # Cross-reference: KeepAlive + crashed = crash loop
    crashed_labels = {label for label, _ in crashed_services}
    for label, plist_file in keepalive_services:
        if label in crashed_labels:
            status = next(s for lbl, s in crashed_services if lbl == label)
            result.findings.append(Finding(
                check="launch_agents",
                severity=Severity.CRITICAL,
                summary=f"{label}: crash-looping (KeepAlive + exit code {status})",
                details=f"Plist: {plist_file}",
                fix=crash_loop_fix(label, str(plist_file), ctx),
            ))

    # Report other crashed services (non-KeepAlive, less severe)
    keepalive_labels = {label for label, _ in keepalive_services}
    for label, status in crashed_services[:10]:  # cap output
        if label not in keepalive_labels:
            result.findings.append(Finding(
                check="launch_agents",
                severity=Severity.INFO,
                summary=f"{label}: exited with status {status}",
            ))

    if not any(f.severity in (Severity.CRITICAL, Severity.WARNING) for f in result.findings):
        result.findings.insert(0, Finding(
            check="launch_agents",
            severity=Severity.OK,
            summary="No crash-looping launch agents detected",
        ))

    return result
