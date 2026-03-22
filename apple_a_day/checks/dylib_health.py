"""Check for broken dynamic library links in Homebrew packages."""

import subprocess
from pathlib import Path

from ..models import CheckResult, Finding, Severity


def check_dylib_health() -> CheckResult:
    """Find Homebrew binaries with missing dylib dependencies."""
    result = CheckResult(name="Dynamic Library Health")

    cellar = Path("/opt/homebrew/Cellar")
    if not cellar.exists():
        cellar = Path("/usr/local/Cellar")
    if not cellar.exists():
        result.findings.append(Finding(
            check="dylib_health",
            severity=Severity.OK,
            summary="No Homebrew Cellar found — skipping dylib check",
        ))
        return result

    # Check binaries in Homebrew-linked services
    broken = []
    checked = 0
    bin_dir = cellar.parent / "bin"

    if bin_dir.exists():
        for binary in bin_dir.iterdir():
            if not binary.is_file() or not binary.is_symlink():
                continue
            real = binary.resolve()
            if not real.exists():
                continue

            try:
                out = subprocess.run(
                    ["otool", "-L", str(real)],
                    capture_output=True, text=True, timeout=5,
                )
                checked += 1
                for line in out.stdout.strip().split("\n")[1:]:
                    lib_path = line.strip().split(" (")[0].strip()
                    if lib_path.startswith("/opt/homebrew") or lib_path.startswith("/usr/local"):
                        if not Path(lib_path).exists():
                            broken.append((binary.name, lib_path))
            except (subprocess.TimeoutExpired, OSError):
                continue

    for binary_name, missing_lib in broken:
        lib_name = Path(missing_lib).name
        result.findings.append(Finding(
            check="dylib_health",
            severity=Severity.CRITICAL,
            summary=f"{binary_name}: missing {lib_name}",
            details=f"Expected at: {missing_lib}",
            fix=f"brew reinstall {binary_name}",
        ))

    if not broken:
        result.findings.append(Finding(
            check="dylib_health",
            severity=Severity.OK,
            summary=f"All {checked} checked binaries have intact dylib links",
        ))

    return result
