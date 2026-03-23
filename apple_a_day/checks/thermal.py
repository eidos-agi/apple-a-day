"""Check thermal pressure and throttling state.

macOS exposes thermal pressure via sysctl. When thermal pressure is
critical, the kernel throttles CPU to prevent hardware damage — this
causes the "my Mac is slow but Activity Monitor doesn't explain why"
experience. kernel_task consuming high CPU is the visible symptom.
"""

import subprocess

from ..models import CheckResult, Finding, Severity


def check_thermal() -> CheckResult:
    """Assess thermal pressure and detect CPU throttling."""
    result = CheckResult(name="Thermal")

    # --- Thermal pressure level ---
    # Try sysctl first (Intel Macs), fall back to pmset (Apple Silicon)
    thermal_found = False
    try:
        out = subprocess.run(
            ["sysctl", "-n", "kern.thermalpressurelevel"],
            capture_output=True, text=True, timeout=5,
        )
        if out.returncode == 0 and out.stdout.strip().isdigit():
            thermal_found = True
            level = int(out.stdout.strip())
            level_map = {
                0: ("nominal", Severity.OK),
                1: ("moderate", Severity.INFO),
                2: ("heavy", Severity.WARNING),
                3: ("trapping", Severity.CRITICAL),
                4: ("sleeping", Severity.CRITICAL),
            }
            label, sev = level_map.get(level, (f"unknown ({level})", Severity.INFO))

            fix = ""
            if sev == Severity.CRITICAL:
                fix = ("Mac is thermally throttled — CPU speed is reduced to prevent damage. "
                       "Move to a cooler surface, check vents aren't blocked, close heavy apps. "
                       "If persistent, SMC reset: shut down, hold power 10s, release, wait 5s, boot.")
            elif sev == Severity.WARNING:
                fix = ("Thermal pressure is elevated — performance may degrade. "
                       "Reduce load or improve airflow.")

            result.findings.append(Finding(
                check="thermal",
                severity=sev,
                summary=f"Thermal pressure: {label}",
                details=f"kern.thermalpressurelevel = {level}",
                fix=fix,
            ))
    except (subprocess.TimeoutExpired, OSError):
        pass

    # Fallback: pmset -g therm (works on Apple Silicon)
    if not thermal_found:
        try:
            out = subprocess.run(
                ["pmset", "-g", "therm"],
                capture_output=True, text=True, timeout=5,
            )
            if out.returncode == 0:
                output = out.stdout.lower()
                if "no thermal warning" in output and "no performance warning" in output:
                    sev = Severity.OK
                    label = "nominal"
                elif "performance warning" in output or "thermal warning" in output:
                    sev = Severity.WARNING
                    label = "elevated"
                else:
                    sev = Severity.OK
                    label = "nominal"

                fix = ""
                if sev == Severity.WARNING:
                    fix = ("Thermal or performance warning active — reduce workload or improve airflow.")

                result.findings.append(Finding(
                    check="thermal",
                    severity=sev,
                    summary=f"Thermal pressure: {label}",
                    details=out.stdout.strip(),
                    fix=fix,
                ))
                thermal_found = True
        except (subprocess.TimeoutExpired, OSError):
            pass

    if not thermal_found:
        result.findings.append(Finding(
            check="thermal",
            severity=Severity.OK,
            summary="Thermal monitoring: no warnings detected",
        ))

    # --- kernel_task CPU usage (thermal throttling indicator) ---
    try:
        out = subprocess.run(
            ["ps", "-eo", "pid,pcpu,comm"],
            capture_output=True, text=True, timeout=5,
        )
        if out.returncode == 0:
            for line in out.stdout.strip().split("\n")[1:]:
                parts = line.split(None, 2)
                if len(parts) >= 3 and parts[2].strip().endswith("kernel_task"):
                    cpu_pct = float(parts[1])
                    if cpu_pct > 200:
                        sev = Severity.CRITICAL
                        summary = f"kernel_task at {cpu_pct:.0f}% CPU — Mac is heavily thermal-throttled"
                    elif cpu_pct > 50:
                        sev = Severity.WARNING
                        summary = f"kernel_task at {cpu_pct:.0f}% CPU — thermal throttling active"
                    elif cpu_pct > 10:
                        sev = Severity.INFO
                        summary = f"kernel_task at {cpu_pct:.0f}% CPU — mild thermal management"
                    else:
                        sev = Severity.OK
                        summary = f"kernel_task at {cpu_pct:.0f}% CPU — normal"

                    fix = ""
                    if sev in (Severity.CRITICAL, Severity.WARNING):
                        fix = ("kernel_task uses CPU to generate idle cycles (heat management). "
                               "Reduce workload, improve ventilation, or use a cooling pad.")

                    result.findings.append(Finding(
                        check="thermal",
                        severity=sev,
                        summary=summary,
                        details=f"kernel_task PID {parts[0]} at {cpu_pct}% CPU",
                        fix=fix,
                    ))
                    break
    except (subprocess.TimeoutExpired, OSError):
        pass

    # --- Fan speed (Apple Silicon doesn't always expose this, but try) ---
    try:
        out = subprocess.run(
            ["powermetrics", "--samplers", "smc", "-n", "1", "-i", "1"],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode == 0 and "Fan" in out.stdout:
            for line in out.stdout.split("\n"):
                if "Fan" in line and "rpm" in line.lower():
                    result.findings.append(Finding(
                        check="thermal",
                        severity=Severity.INFO,
                        summary=line.strip(),
                    ))
                    break
    except (subprocess.TimeoutExpired, OSError, PermissionError):
        # powermetrics requires root — that's fine, skip it
        pass

    if not result.findings:
        result.findings.append(Finding(
            check="thermal",
            severity=Severity.OK,
            summary="Thermal state: normal",
        ))

    return result
