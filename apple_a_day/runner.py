"""Run all health checks and collect results."""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from .checks import ALL_CHECKS, OPT_IN_CHECKS
from .models import CheckError, CheckResult, ERR_TIMEOUT, ERR_UNKNOWN


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
            capture_output=True,
            text=True,
            timeout=5,
        )
        info["cpu"] = out.stdout.strip()
    except (subprocess.TimeoutExpired, OSError):
        pass

    try:
        out = subprocess.run(
            ["sysctl", "-n", "hw.memsize"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        mem_bytes = int(out.stdout.strip())
        info["memory_gb"] = round(mem_bytes / (1024**3))
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

    def _run_check(fn):
        try:
            return fn()
        except TimeoutError:
            return CheckResult(
                name=fn.__name__,
                errors=[
                    CheckError(
                        check=fn.__name__,
                        error_code=ERR_TIMEOUT,
                        message="Check timed out",
                        suggestion="Try running with --no-parallel or check if a subprocess is hanging",
                    )
                ],
            )
        except Exception as e:
            return CheckResult(
                name=fn.__name__,
                errors=[
                    CheckError(
                        check=fn.__name__,
                        error_code=ERR_UNKNOWN,
                        message=str(e),
                        suggestion="Run the check individually to see full output",
                    )
                ],
            )

    if parallel:
        results: list[CheckResult] = []
        with ThreadPoolExecutor(max_workers=min(6, len(ALL_CHECKS))) as pool:
            futures = {pool.submit(_run_check, fn): fn for fn in ALL_CHECKS}
            for future in as_completed(futures):
                results.append(future.result())
        # Preserve consistent ordering (same as ALL_CHECKS)
        order = {fn.__name__: i for i, fn in enumerate(ALL_CHECKS)}
        results.sort(key=lambda r: order.get(r.name, 999))
    else:
        results = [_run_check(fn) for fn in ALL_CHECKS]

    duration_ms = int((time.monotonic() - start) * 1000)

    report = CheckupReport(results=results, duration_ms=duration_ms, mac_info=mac_info)

    # Auto-log every checkup (trigger auto-detected: boot vs scheduled vs manual)
    try:
        from .log import log_checkup

        log_checkup(report)
    except Exception:
        pass  # logging should never break the checkup

    return report
