"""Run all health checks and collect results."""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from .checks import ALL_CHECKS
from .models import CheckResult, Finding, Severity


@dataclass
class CheckupReport:
    """Full checkup results with metadata."""

    results: list[CheckResult]
    duration_ms: int
    mac_info: dict


def get_mac_info() -> dict:
    """Collect basic Mac identification."""
    import platform
    import subprocess

    info = {
        "os_version": platform.mac_ver()[0],
        "arch": platform.machine(),
        "hostname": platform.node(),
    }

    try:
        out = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            capture_output=True, text=True, timeout=5,
        )
        info["cpu"] = out.stdout.strip()
    except (subprocess.TimeoutExpired, OSError):
        pass

    try:
        out = subprocess.run(
            ["sysctl", "-n", "hw.memsize"],
            capture_output=True, text=True, timeout=5,
        )
        mem_bytes = int(out.stdout.strip())
        info["memory_gb"] = round(mem_bytes / (1024 ** 3))
    except (subprocess.TimeoutExpired, OSError, ValueError):
        pass

    return info


def run_all_checks(parallel: bool = True) -> CheckupReport:
    """Execute every registered health check and return results.

    Checks run in parallel by default since they're independent I/O-bound
    operations (subprocess calls to native tools). This cuts total checkup
    time roughly in half.
    """
    start = time.monotonic()
    mac_info = get_mac_info()

    if parallel:
        results: list[CheckResult] = []
        with ThreadPoolExecutor(max_workers=len(ALL_CHECKS)) as pool:
            futures = {pool.submit(fn): fn for fn in ALL_CHECKS}
            for future in as_completed(futures):
                fn = futures[future]
                try:
                    results.append(future.result(timeout=30))
                except Exception:
                    results.append(CheckResult(
                        name=fn.__name__,
                        findings=[Finding(
                            check=fn.__name__,
                            severity=Severity.INFO,
                            summary=f"Check failed to complete",
                        )],
                    ))
        # Preserve consistent ordering (same as ALL_CHECKS)
        order = {fn.__name__: i for i, fn in enumerate(ALL_CHECKS)}
        results.sort(key=lambda r: order.get(r.name, 999))
    else:
        results = []
        for check_fn in ALL_CHECKS:
            try:
                results.append(check_fn())
            except Exception:
                results.append(CheckResult(name=check_fn.__name__))

    duration_ms = int((time.monotonic() - start) * 1000)

    return CheckupReport(results=results, duration_ms=duration_ms, mac_info=mac_info)
