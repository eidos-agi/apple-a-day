"""Check Homebrew health: outdated packages, doctor warnings, orphans."""

import subprocess

from ..models import CheckResult, Finding, Severity


def check_homebrew() -> CheckResult:
    """Run brew doctor and check for orphaned/outdated packages."""
    result = CheckResult(name="Homebrew")

    # Check if brew exists
    try:
        subprocess.run(["brew", "--version"], capture_output=True, timeout=5)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        result.findings.append(
            Finding(
                check="homebrew",
                severity=Severity.OK,
                summary="Homebrew not installed — skipping",
            )
        )
        return result

    # brew doctor
    try:
        out = subprocess.run(
            ["brew", "doctor"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if out.returncode != 0:
            warnings = [line for line in out.stderr.split("\n") if line.startswith("Warning:")]
            for w in warnings[:5]:
                result.findings.append(
                    Finding(
                        check="homebrew",
                        severity=Severity.WARNING,
                        summary=w.replace("Warning: ", ""),
                        fix="Run `brew doctor` for full details.",
                    )
                )
        else:
            result.findings.append(
                Finding(
                    check="homebrew",
                    severity=Severity.OK,
                    summary="brew doctor: all clear",
                )
            )
    except subprocess.TimeoutExpired:
        result.findings.append(
            Finding(
                check="homebrew",
                severity=Severity.INFO,
                summary="brew doctor timed out",
            )
        )

    # Outdated packages
    try:
        out = subprocess.run(
            ["brew", "outdated", "--json=v2"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if out.stdout:
            import json

            data = json.loads(out.stdout)
            formulae = data.get("formulae", [])
            casks = data.get("casks", [])
            total = len(formulae) + len(casks)
            if total > 0:
                sev = Severity.INFO if total < 20 else Severity.WARNING
                result.findings.append(
                    Finding(
                        check="homebrew",
                        severity=sev,
                        summary=f"{total} outdated packages ({len(formulae)} formulae, {len(casks)} casks)",
                        fix="Run `brew upgrade` to update.",
                    )
                )
    except (subprocess.TimeoutExpired, OSError):
        pass

    return result
