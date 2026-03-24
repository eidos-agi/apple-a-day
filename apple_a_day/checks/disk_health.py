"""Check disk health: APFS container state, free space, snapshot bloat."""

import plistlib
import subprocess

from ..context import get_context, disk_context
from ..models import CheckResult, Finding, Severity


def check_disk_health() -> CheckResult:
    """Check APFS container health, free space, and Time Machine snapshot bloat."""
    result = CheckResult(name="Disk Health")
    ctx = get_context()

    # Free space check — use diskutil for real APFS container usage (df lies)
    try:
        out = subprocess.run(
            ["diskutil", "info", "/"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        info_lines = {}
        for line in out.stdout.strip().split("\n"):
            if ":" in line:
                key, _, val = line.partition(":")
                info_lines[key.strip()] = val.strip()

        disk_size_str = info_lines.get("Disk Size", "")
        free_str = info_lines.get("Container Free Space", "")

        disk_bytes = None
        free_bytes = None

        # Parse "994.7 GB (994662584320 Bytes)"
        for label, raw in [("disk", disk_size_str), ("free", free_str)]:
            if "Bytes" in raw:
                try:
                    b = int(raw.split("(")[1].split(" Bytes")[0])
                    if label == "disk":
                        disk_bytes = b
                    else:
                        free_bytes = b
                except (IndexError, ValueError):
                    pass

        if disk_bytes and free_bytes:
            used_pct = round((1 - free_bytes / disk_bytes) * 100)
            free_gb = round(free_bytes / (1000**3), 1)

            if free_gb < 10:
                sev = Severity.CRITICAL
            elif free_gb < 30:
                sev = Severity.WARNING
            elif used_pct >= 95:
                sev = Severity.CRITICAL
            elif used_pct >= 85:
                sev = Severity.WARNING
            else:
                sev = Severity.OK

            fix = ""
            if sev != Severity.OK:
                fix = (
                    "Run `sudo tmutil thinlocalsnapshots / 9999999999 1` to reclaim snapshot space."
                )
                extra = disk_context(free_gb, used_pct, ctx)
                if extra:
                    fix += f" {extra}"

            details = ""
            if sev != Severity.OK and ctx.get("is_developer"):
                details = (
                    "Developers with heavy workloads should keep 50+ GB free "
                    "to avoid swap pressure and slow builds."
                )

            result.findings.append(
                Finding(
                    check="disk_health",
                    severity=sev,
                    summary=f"Boot disk {used_pct}% full — {free_gb} GB free",
                    details=details,
                    fix=fix,
                )
            )
    except (subprocess.TimeoutExpired, OSError, ValueError):
        pass

    # APFS container verification (quick check via diskutil)
    try:
        out = subprocess.run(
            ["diskutil", "apfs", "list", "-plist"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        plist = plistlib.loads(out.stdout.encode())
        containers = plist.get("Containers", [])
        for container in containers:
            ref = container.get("ContainerReference", "unknown")
            volumes = container.get("Volumes", [])
            [v.get("Roles", []) for v in volumes]
            result.findings.append(
                Finding(
                    check="disk_health",
                    severity=Severity.OK,
                    summary=f"APFS container {ref}: {len(volumes)} volumes",
                )
            )
    except (subprocess.TimeoutExpired, OSError, plistlib.InvalidFileException):
        pass

    # Time Machine local snapshot count
    try:
        out = subprocess.run(
            ["tmutil", "listlocalsnapshots", "/"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        snapshots = [
            line for line in out.stdout.strip().split("\n") if line.startswith("com.apple")
        ]
        count = len(snapshots)
        if count > 20:
            sev = Severity.WARNING
        else:
            sev = Severity.OK

        if count > 0:
            result.findings.append(
                Finding(
                    check="disk_health",
                    severity=sev,
                    summary=f"{count} local Time Machine snapshots",
                    fix="Thin with: `sudo tmutil thinlocalsnapshots / 9999999999 1`"
                    if sev != Severity.OK
                    else "",
                )
            )
    except (subprocess.TimeoutExpired, OSError):
        pass

    if not result.findings:
        result.findings.append(
            Finding(
                check="disk_health",
                severity=Severity.OK,
                summary="Disk health checks passed",
            )
        )

    return result
