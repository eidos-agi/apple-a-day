"""Check system memory pressure and swap usage."""

import subprocess

from ..context import get_context, swap_thresholds
from ..models import CheckResult, Finding, Severity


def check_memory_pressure() -> CheckResult:
    """Assess current memory pressure level and swap usage."""
    result = CheckResult(name="Memory Pressure")
    ctx = get_context()

    # Get memory pressure level
    try:
        out = subprocess.run(
            ["/usr/bin/memory_pressure", "-Q"],
            capture_output=True,
            text=True,
            timeout=10,
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

        fix = ""
        if severity != Severity.OK:
            fix = "Close memory-heavy apps or check for leaks with `leaks <pid>`"
            if ctx.get("is_docker_user"):
                fix += ". Docker Desktop often holds significant RAM — check its resource limits."
            if ctx.get("is_ai_user"):
                fix += ". Local LLM models (Ollama) can consume 4-16 GB each."

        result.findings.append(
            Finding(
                check="memory_pressure",
                severity=severity,
                summary=f"Memory pressure: {level}",
                details=out.stdout.strip().split("\n")[-1] if out.stdout else "",
                fix=fix,
            )
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        result.findings.append(
            Finding(
                check="memory_pressure",
                severity=Severity.INFO,
                summary=f"Could not read memory pressure: {e}",
            )
        )

    # Check swap usage via sysctl
    try:
        out = subprocess.run(
            ["sysctl", "vm.swapusage"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        parts = out.stdout.strip()
        if "used" in parts:
            used_str = parts.split("used = ")[1].split(" ")[0]
            used_val = float(used_str.rstrip("M"))

            # Profile-aware thresholds scaled to RAM size
            warn_mb, crit_mb = swap_thresholds(ctx)

            if used_val > crit_mb:
                sev = Severity.CRITICAL
            elif used_val > warn_mb:
                sev = Severity.WARNING
            else:
                sev = Severity.OK

            fix = ""
            if sev != Severity.OK:
                ram = ctx.get("memory_gb", "?")
                fix = (
                    f"Swap at {used_str}M with {ram} GB RAM — "
                    f"your Mac is running on SSD, not memory. "
                    f"Reboot to clear swap, then find the memory hog."
                )

            result.findings.append(
                Finding(
                    check="memory_pressure",
                    severity=sev,
                    summary=f"Swap usage: {used_str}M",
                    details=parts,
                    fix=fix,
                )
            )
    except (subprocess.TimeoutExpired, OSError, ValueError, IndexError):
        pass

    return result
