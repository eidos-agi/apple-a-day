"""Check CPU load average and identify resource-hogging processes.

This is the check that catches the "my Mac is unresponsive" scenario —
load average far exceeding core count, with identifiable culprits.
"""

import os
import subprocess

from ..models import CheckResult, Finding, Severity


def check_cpu_load() -> CheckResult:
    """Assess CPU load relative to core count, flag resource hogs."""
    result = CheckResult(name="CPU Load")
    cores = os.cpu_count() or 8

    # --- Load average ---
    try:
        loadavg = os.getloadavg()  # (1m, 5m, 15m)
        load_1, load_5, load_15 = loadavg

        ratio = load_1 / cores
        if ratio > 10:
            sev = Severity.CRITICAL
            summary = (
                f"Load average {load_1:.0f} is {ratio:.0f}x your {cores} cores — "
                f"machine is severely overloaded"
            )
        elif ratio > 3:
            sev = Severity.WARNING
            summary = (
                f"Load average {load_1:.0f} is {ratio:.1f}x your {cores} cores — "
                f"system is struggling"
            )
        elif ratio > 1.5:
            sev = Severity.INFO
            summary = f"Load average {load_1:.1f} is moderately high ({ratio:.1f}x {cores} cores)"
        else:
            sev = Severity.OK
            summary = f"Load average {load_1:.1f} — healthy for {cores} cores"

        fix = ""
        if sev in (Severity.CRITICAL, Severity.WARNING):
            fix = "Identify top processes below and kill or throttle the worst offenders"
            # Detect sustained vs spike
            if load_15 > cores * 3:
                fix += f". Load has been high for 15+ minutes ({load_15:.0f}) — this is sustained, not a spike"
            elif load_1 > cores * 5 and load_15 < cores * 2:
                fix += ". This looks like a recent spike — may resolve on its own"

        result.findings.append(
            Finding(
                check="cpu_load",
                severity=sev,
                summary=summary,
                details=f"1m: {load_1:.1f}  5m: {load_5:.1f}  15m: {load_15:.1f}  cores: {cores}",
                fix=fix,
            )
        )
    except OSError:
        result.findings.append(
            Finding(
                check="cpu_load",
                severity=Severity.INFO,
                summary="Could not read load average",
            )
        )

    # --- Top CPU consumers ---
    try:
        out = subprocess.run(
            ["ps", "-eo", "pid,pcpu,pmem,comm", "-r"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if out.returncode == 0:
            lines = out.stdout.strip().split("\n")[1:]  # skip header
            hogs = []
            for line in lines[:20]:  # top 20
                parts = line.split(None, 3)
                if len(parts) < 4:
                    continue
                pid, cpu, mem, comm = parts
                cpu_pct = float(cpu)
                if cpu_pct < 10:
                    break  # sorted by CPU desc, stop when below 10%
                proc_name = comm.rsplit("/", 1)[-1]  # basename
                hogs.append((pid, cpu_pct, float(mem), proc_name))

            if hogs:
                # Categorize known offenders
                categorized = _categorize_hogs(hogs)
                total_cpu = sum(h[1] for h in hogs)

                if total_cpu > cores * 100 * 0.8:
                    sev = Severity.CRITICAL
                elif total_cpu > cores * 100 * 0.5:
                    sev = Severity.WARNING
                else:
                    sev = Severity.INFO

                details_lines = []
                for pid, cpu_pct, mem_pct, name in hogs:
                    tag = categorized.get(name, "")
                    tag_str = f" [{tag}]" if tag else ""
                    details_lines.append(
                        f"  {name:30s} {cpu_pct:5.1f}% CPU  {mem_pct:4.1f}% MEM  (PID {pid}){tag_str}"
                    )

                fix = ""
                if sev != Severity.OK:
                    killable = [
                        n for n, t in categorized.items() if t in ("cloud-sync", "vm", "build")
                    ]
                    if killable:
                        fix = f"Consider stopping: {', '.join(killable)}"
                    else:
                        fix = "Review top consumers — kill or defer non-essential work"

                result.findings.append(
                    Finding(
                        check="cpu_load",
                        severity=sev,
                        summary=f"{len(hogs)} process{'es' if len(hogs) != 1 else ''} using >10% CPU (total: {total_cpu:.0f}%)",
                        details="\n".join(details_lines),
                        fix=fix,
                    )
                )
            else:
                result.findings.append(
                    Finding(
                        check="cpu_load",
                        severity=Severity.OK,
                        summary="No processes above 10% CPU",
                    )
                )
    except (subprocess.TimeoutExpired, OSError):
        pass

    return result


def _categorize_hogs(hogs: list[tuple]) -> dict[str, str]:
    """Tag known processes with human-readable categories."""
    categories = {
        # Cloud sync
        "fileproviderd": "cloud-sync",
        "OneDrive": "cloud-sync",
        "Dropbox": "cloud-sync",
        "bird": "cloud-sync",  # iCloud
        "cloudd": "cloud-sync",
        # VMs
        "prl_client_app": "vm",
        "prl_disp_service": "vm",
        "prl_vm_app": "vm",
        "VBoxHeadless": "vm",
        "qemu-system-aarch64": "vm",
        "com.docker.hyperkit": "vm",
        "Docker Desktop": "vm",
        # Build tools
        "xcodebuild": "build",
        "clang": "build",
        "swift": "build",
        "rustc": "build",
        "cargo": "build",
        "gcc": "build",
        "make": "build",
        "ninja": "build",
        # Browsers
        "Google Chrome Helper": "browser",
        "Safari": "browser",
        "firefox": "browser",
        # System
        "trustd": "system-security",
        "mds_stores": "spotlight",
        "mdworker_shared": "spotlight",
        "WindowServer": "system-graphics",
        "kernel_task": "system-thermal",
        # Dev services
        "node": "dev-service",
        "python3": "dev-service",
        "uvicorn": "dev-service",
        "ruby": "dev-service",
    }

    result = {}
    for _, _, _, name in hogs:
        if name in categories:
            result[name] = categories[name]
        # Partial match for helper processes
        elif "Chrome" in name:
            result[name] = "browser"
        elif "Docker" in name:
            result[name] = "vm"
        elif "Parallels" in name or "prl_" in name:
            result[name] = "vm"
    return result
