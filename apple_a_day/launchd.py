"""Install/uninstall the apple-a-day vitals monitor as a launchd service.

Runs `aad monitor --once` every 60 seconds, building up the time-series
data that powers the sustained pressure analysis in the report.
"""

import os
import subprocess
import sys
from pathlib import Path

PLIST_NAME = "com.eidos.apple-a-day"
PLIST_DIR = Path.home() / "Library" / "LaunchAgents"


def _plist_path() -> Path:
    return PLIST_DIR / f"{PLIST_NAME}.plist"


def _find_aad() -> str:
    """Find the aad executable path."""
    # Check if aad is on PATH
    try:
        out = subprocess.run(["which", "aad"], capture_output=True, text=True, timeout=5)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (subprocess.TimeoutExpired, OSError):
        pass
    # Fallback: python -m
    return sys.executable


def generate_plist() -> str:
    """Generate the launchd plist XML."""
    aad_path = _find_aad()
    log_dir = Path.home() / ".config" / "eidos" / "aad-logs"

    # If aad binary found, use it directly. Otherwise use python -m
    if aad_path.endswith("aad"):
        program_args = f"""    <array>
        <string>{aad_path}</string>
        <string>monitor</string>
        <string>--once</string>
    </array>"""
    else:
        program_args = f"""    <array>
        <string>{aad_path}</string>
        <string>-m</string>
        <string>apple_a_day.cli</string>
        <string>monitor</string>
        <string>--once</string>
    </array>"""

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{PLIST_NAME}</string>

    <key>ProgramArguments</key>
{program_args}

    <!-- Sample every 60 seconds -->
    <key>StartInterval</key>
    <integer>60</integer>

    <key>RunAtLoad</key>
    <true/>

    <key>StandardOutPath</key>
    <string>{log_dir}/monitor.log</string>
    <key>StandardErrorPath</key>
    <string>{log_dir}/monitor.err</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>{os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin")}</string>
    </dict>
</dict>
</plist>"""


def install() -> str:
    """Install and start the vitals monitor daemon."""
    PLIST_DIR.mkdir(parents=True, exist_ok=True)
    plist = _plist_path()
    plist.write_text(generate_plist())

    # Load it
    uid = os.getuid()
    subprocess.run(
        ["launchctl", "bootstrap", f"gui/{uid}", str(plist)], capture_output=True, timeout=10
    )

    return f"Installed: {plist}\nSampling vitals every 60s → ~/.config/eidos/aad-logs/vitals.ndjson"


def uninstall() -> str:
    """Stop and remove the vitals monitor daemon."""
    plist = _plist_path()
    uid = os.getuid()

    subprocess.run(
        ["launchctl", "bootout", f"gui/{uid}", str(plist)], capture_output=True, timeout=10
    )

    if plist.exists():
        plist.unlink()

    return f"Removed: {plist}"


def status() -> str:
    """Check if the monitor daemon is running."""
    try:
        out = subprocess.run(["launchctl", "list"], capture_output=True, text=True, timeout=10)
        for line in out.stdout.strip().split("\n"):
            if PLIST_NAME in line:
                parts = line.split("\t")
                pid = parts[0] if parts[0] != "-" else "not running"
                exit_code = parts[1]
                return f"Status: PID={pid}, last exit={exit_code}"
    except (subprocess.TimeoutExpired, OSError):
        pass

    if _plist_path().exists():
        return "Installed but not loaded"
    return "Not installed. Run `aad install` to start collecting vitals."
