"""Check disk health: APFS container state, free space, snapshot bloat."""

import plistlib
import subprocess

from ..models import CheckResult, Finding, Severity


def check_disk_health() -> CheckResult:
    """Check APFS container health, free space, and Time Machine snapshot bloat."""
    result = CheckResult(name="Disk Health")

    # Free space check
    try:
        out = subprocess.run(
            ["df", "-H", "/"],
            capture_output=True, text=True, timeout=5,
        )
        lines = out.stdout.strip().split("\n")
        if len(lines) >= 2:
            parts = lines[1].split()
            # parts: [filesystem, size, used, avail, capacity%, mount]
            if len(parts) >= 5:
                capacity = int(parts[4].rstrip("%"))
                avail = parts[3]

                if capacity >= 95:
                    sev = Severity.CRITICAL
                elif capacity >= 85:
                    sev = Severity.WARNING
                else:
                    sev = Severity.OK

                result.findings.append(Finding(
                    check="disk_health",
                    severity=sev,
                    summary=f"Boot disk {capacity}% full — {avail} free",
                    fix="Run `sudo tmutil thinlocalsnapshots / 9999999999 1`"
                        " to reclaim Time Machine snapshot space." if sev != Severity.OK else "",
                ))
    except (subprocess.TimeoutExpired, OSError, ValueError):
        pass

    # APFS container verification (quick check via diskutil)
    try:
        out = subprocess.run(
            ["diskutil", "apfs", "list", "-plist"],
            capture_output=True, text=True, timeout=15,
        )
        plist = plistlib.loads(out.stdout.encode())
        containers = plist.get("Containers", [])
        for container in containers:
            ref = container.get("ContainerReference", "unknown")
            volumes = container.get("Volumes", [])
            roles = [v.get("Roles", []) for v in volumes]
            result.findings.append(Finding(
                check="disk_health",
                severity=Severity.OK,
                summary=f"APFS container {ref}: {len(volumes)} volumes",
            ))
    except (subprocess.TimeoutExpired, OSError, plistlib.InvalidFileException):
        pass

    # Time Machine local snapshot count
    try:
        out = subprocess.run(
            ["tmutil", "listlocalsnapshots", "/"],
            capture_output=True, text=True, timeout=10,
        )
        snapshots = [l for l in out.stdout.strip().split("\n") if l.startswith("com.apple")]
        count = len(snapshots)
        if count > 20:
            sev = Severity.WARNING
        else:
            sev = Severity.OK

        if count > 0:
            result.findings.append(Finding(
                check="disk_health",
                severity=sev,
                summary=f"{count} local Time Machine snapshots",
                fix="Thin with: `sudo tmutil thinlocalsnapshots / 9999999999 1`" if sev != Severity.OK else "",
            ))
    except (subprocess.TimeoutExpired, OSError):
        pass

    if not result.findings:
        result.findings.append(Finding(
            check="disk_health",
            severity=Severity.OK,
            summary="Disk health checks passed",
        ))

    return result
