"""Check system memory pressure and swap usage."""

import subprocess

from ..models import CheckResult, Finding, Severity


def check_memory_pressure() -> CheckResult:
    """Assess current memory pressure level and swap usage."""
    result = CheckResult(name="Memory Pressure")

    # Get memory pressure level
    try:
        out = subprocess.run(
            ["/usr/bin/memory_pressure", "-Q"],
            capture_output=True, text=True, timeout=10,
        )
        output = out.stdout.lower()

        if "critical" in output:
            level, severity = "CRITICAL", Severity.CRITICAL
        elif "warn" in output:
            level, severity = "WARNING", Severity.WARNING
        elif "normal" in output:
            level, severity = "normal", Severity.OK
        else:
            level, severity = "unknown", Severity.INFO

        result.findings.append(Finding(
            check="memory_pressure",
            severity=severity,
            summary=f"Memory pressure: {level}",
            details=out.stdout.strip().split("\n")[-1] if out.stdout else "",
            fix="Close memory-heavy apps or check for leaks with `leaks <pid>`" if severity != Severity.OK else "",
        ))
    except (subprocess.TimeoutExpired, OSError) as e:
        result.findings.append(Finding(
            check="memory_pressure",
            severity=Severity.INFO,
            summary=f"Could not read memory pressure: {e}",
        ))

    # Check swap usage via sysctl
    try:
        out = subprocess.run(
            ["sysctl", "vm.swapusage"],
            capture_output=True, text=True, timeout=5,
        )
        # Output: "vm.swapusage: total = 2048.00M  used = 512.00M  free = 1536.00M ..."
        parts = out.stdout.strip()
        if "used" in parts:
            used_str = parts.split("used = ")[1].split(" ")[0]
            used_val = float(used_str.rstrip("M"))

            if used_val > 4000:
                sev = Severity.WARNING
            elif used_val > 8000:
                sev = Severity.CRITICAL
            else:
                sev = Severity.OK

            result.findings.append(Finding(
                check="memory_pressure",
                severity=sev,
                summary=f"Swap usage: {used_str}M",
                details=parts,
                fix="High swap causes SSD wear and slowdowns." if sev != Severity.OK else "",
            ))
    except (subprocess.TimeoutExpired, OSError, ValueError, IndexError):
        pass

    return result
