"""Check recent shutdown/crash causes from system logs.

macOS logs why the system shut down. Common causes:
  3: soft reboot (normal)
  5: hard shutdown (power button / force off)
  -1 or -2: kernel panic
  -3: thermal emergency
  -64: low battery
  -128: unknown / forced

This check reads the last few shutdown causes and flags abnormal ones.
"""

import re
import subprocess

from ..models import CheckResult, Finding, Severity

# https://support.apple.com/en-us/102758
_CAUSE_MAP = {
    "3": ("clean reboot", Severity.OK),
    "5": ("clean shutdown (power button)", Severity.OK),
    "7": ("sleep wake failure or CPU watchdog", Severity.WARNING),
    "0": ("power restored after outage", Severity.INFO),
    "-1": ("kernel panic", Severity.CRITICAL),
    "-2": ("kernel panic (watchdog)", Severity.CRITICAL),
    "-3": ("thermal emergency shutdown", Severity.CRITICAL),
    "-62": ("bridgeOS crash (T2/firmware)", Severity.CRITICAL),
    "-64": ("low battery emergency shutdown", Severity.WARNING),
    "-71": ("SOC watchdog", Severity.CRITICAL),
    "-74": ("temperature too high", Severity.CRITICAL),
    "-104": ("battery health failure", Severity.WARNING),
    "-128": ("unknown cause (forced power off?)", Severity.WARNING),
}


def check_shutdown_causes() -> CheckResult:
    """Analyze recent shutdown reasons from system logs."""
    result = CheckResult(name="Shutdown Causes")

    # Method 1: log show for shutdown cause entries
    causes = []
    try:
        out = subprocess.run(
            ["log", "show", "--predicate",
             'eventMessage contains "Previous shutdown cause"',
             "--style", "compact", "--last", "7d"],
            capture_output=True, text=True, timeout=30,
        )
        if out.returncode == 0:
            for line in out.stdout.strip().split("\n"):
                m = re.search(r"Previous shutdown cause:\s*(-?\d+)", line)
                if m:
                    code = m.group(1)
                    # Extract timestamp (first field in compact format)
                    ts = line.split(None, 1)[0] if line else ""
                    causes.append((ts, code))
    except (subprocess.TimeoutExpired, OSError):
        pass

    # Method 2: sysctl for last shutdown cause (always available)
    if not causes:
        try:
            out = subprocess.run(
                ["sysctl", "-n", "kern.shutdownreason"],
                capture_output=True, text=True, timeout=5,
            )
            if out.returncode == 0 and out.stdout.strip():
                causes.append(("last boot", out.stdout.strip()))
        except (subprocess.TimeoutExpired, OSError):
            pass

    if not causes:
        result.findings.append(Finding(
            check="shutdown_causes",
            severity=Severity.OK,
            summary="No recent shutdown events found in logs",
        ))
        return result

    # Analyze causes
    abnormal = []
    for ts, code in causes:
        label, sev = _CAUSE_MAP.get(code, (f"unknown code {code}", Severity.INFO))
        if sev in (Severity.CRITICAL, Severity.WARNING):
            abnormal.append((ts, code, label, sev))

    if abnormal:
        worst = max(abnormal, key=lambda x: list(Severity).index(x[3]))
        ts, code, label, sev = worst

        details_lines = [f"  {ts}: cause {code} ({label})" for ts, code, label, _ in abnormal]
        if len(causes) > len(abnormal):
            clean = len(causes) - len(abnormal)
            details_lines.append(f"  + {clean} clean shutdown(s)")

        fix = _fix_for_cause(worst[1])

        result.findings.append(Finding(
            check="shutdown_causes",
            severity=sev,
            summary=f"{len(abnormal)} abnormal shutdown(s) in the last 7 days — worst: {label}",
            details="\n".join(details_lines),
            fix=fix,
        ))
    else:
        result.findings.append(Finding(
            check="shutdown_causes",
            severity=Severity.OK,
            summary=f"All {len(causes)} recent shutdown(s) were clean",
        ))

    return result


def _fix_for_cause(code: str) -> str:
    """Return a targeted fix suggestion for a shutdown cause code."""
    fixes = {
        "-1": ("Kernel panic — run `aad checkup -c kernel_panics` for details. "
               "Check for bad RAM, faulty peripherals, or kext issues."),
        "-2": ("Watchdog-triggered kernel panic — a subsystem hung for too long. "
               "Check for stuck I/O (external drives, network mounts)."),
        "-3": ("Thermal emergency — Mac shut down to prevent hardware damage. "
               "Check fans, vents, and ambient temperature. "
               "Run `aad checkup -c thermal` for current thermal state."),
        "-74": ("Temperature sensor triggered shutdown. "
               "Same as thermal emergency — check cooling and workload."),
        "-62": "bridgeOS/T2 crash — firmware issue. Check for macOS updates.",
        "-71": "SOC watchdog — Apple Silicon subsystem timeout. Check for macOS updates.",
        "-64": "Battery ran out. Check battery health in System Information.",
        "-104": "Battery health triggered shutdown. Check battery cycle count and consider replacement.",
        "-128": ("Forced power off — either user held power button or system lost power. "
                "If you didn't do this, check power supply and sleep/wake issues."),
        "7": ("Sleep/wake failure — Mac couldn't wake properly. "
              "Check for peripherals that interfere with sleep, or disable Power Nap."),
    }
    return fixes.get(code, "Investigate the shutdown cause code in Console.app or `log show`.")
