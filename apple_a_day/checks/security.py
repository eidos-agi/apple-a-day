"""Check macOS security posture: SIP, Gatekeeper, FileVault, XProtect."""

import subprocess

from ..models import CheckResult, Finding, Severity


def check_security() -> CheckResult:
    """Check System Integrity Protection, Gatekeeper, FileVault, and XProtect status."""
    result = CheckResult(name="Security")

    # SIP (System Integrity Protection)
    try:
        out = subprocess.run(
            ["csrutil", "status"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        output = out.stdout.strip().lower()
        if "enabled" in output:
            result.findings.append(
                Finding(
                    check="security",
                    severity=Severity.OK,
                    summary="System Integrity Protection: enabled",
                )
            )
        elif "disabled" in output:
            result.findings.append(
                Finding(
                    check="security",
                    severity=Severity.CRITICAL,
                    summary="System Integrity Protection: DISABLED",
                    details="SIP protects core system files from modification. Disabling it exposes your Mac to rootkits and malware.",
                    fix="Reboot into Recovery Mode (hold Power button), open Terminal, run: csrutil enable",
                )
            )
        else:
            result.findings.append(
                Finding(
                    check="security",
                    severity=Severity.INFO,
                    summary=f"SIP status unclear: {out.stdout.strip()[:80]}",
                )
            )
    except (subprocess.TimeoutExpired, OSError):
        pass

    # Gatekeeper
    try:
        out = subprocess.run(
            ["spctl", "--status"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        output = out.stdout.strip().lower() + out.stderr.strip().lower()
        if "assessments enabled" in output:
            result.findings.append(
                Finding(
                    check="security",
                    severity=Severity.OK,
                    summary="Gatekeeper: enabled",
                )
            )
        elif "assessments disabled" in output:
            result.findings.append(
                Finding(
                    check="security",
                    severity=Severity.WARNING,
                    summary="Gatekeeper: disabled",
                    details="Gatekeeper blocks unnotarized apps. Without it, any downloaded app can run.",
                    fix="sudo spctl --master-enable",
                )
            )
    except (subprocess.TimeoutExpired, OSError):
        pass

    # FileVault
    try:
        out = subprocess.run(
            ["fdesetup", "status"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        output = out.stdout.strip()
        if "On" in output:
            result.findings.append(
                Finding(
                    check="security",
                    severity=Severity.OK,
                    summary="FileVault: enabled (disk encryption active)",
                )
            )
        elif "Off" in output:
            result.findings.append(
                Finding(
                    check="security",
                    severity=Severity.WARNING,
                    summary="FileVault: OFF — disk is not encrypted",
                    details="If your Mac is lost or stolen, anyone can read your files.",
                    fix="System Settings → Privacy & Security → FileVault → Turn On",
                )
            )
    except (subprocess.TimeoutExpired, OSError):
        pass

    # XProtect version — read directly from bundle plist (instant, no system_profiler)
    try:
        import plistlib
        from pathlib import Path

        xprotect_plist = Path(
            "/Library/Apple/System/Library/CoreServices/XProtect.bundle/Contents/version.plist"
        )
        if xprotect_plist.exists():
            with open(xprotect_plist, "rb") as f:
                info = plistlib.load(f)
            version = info.get("CFBundleShortVersionString", "unknown")
            result.findings.append(
                Finding(
                    check="security",
                    severity=Severity.OK,
                    summary=f"XProtect: version {version}",
                    details="XProtect updates are applied automatically by macOS.",
                )
            )
        else:
            result.findings.append(
                Finding(
                    check="security",
                    severity=Severity.INFO,
                    summary="XProtect: bundle not found at expected path",
                )
            )
    except (OSError, ValueError):
        pass

    if not result.findings:
        result.findings.append(
            Finding(
                check="security",
                severity=Severity.INFO,
                summary="Could not determine security status",
            )
        )

    return result
