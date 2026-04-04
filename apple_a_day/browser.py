"""Browser extension native host management for apple-a-day.

Installs/uninstalls the Chrome Native Messaging Host that bridges
the browser extension to the local NDJSON log at
~/.config/eidos/aad-logs/browser.ndjson.

Usage:
    aad browser install
    aad browser uninstall
    aad browser status
"""

import json
import shutil
import stat
from pathlib import Path

# Deterministic extension ID derived from the key in manifest.json
EXTENSION_ID = "gbfkgnkmnohlnokcmjjhhbbmofggpikc"

# Where Chrome looks for native messaging host manifests on macOS
CHROME_NMH_DIR = (
    Path.home() / "Library" / "Application Support" / "Google" / "Chrome" / "NativeMessagingHosts"
)
MANIFEST_NAME = "com.eidos.aad.browser.json"

# Where we install the host script
HOST_DIR = Path.home() / ".config" / "eidos" / "aad-browser-host"
HOST_SCRIPT = HOST_DIR / "aad_browser_host.py"

# Source files (relative to this module — the browser/ dir in the repo)
_REPO_BROWSER_DIR = Path(__file__).parent.parent / "browser" / "native-host"


def install(extension_id: str | None = None) -> str:
    """Install the native messaging host."""
    ext_id = extension_id or EXTENSION_ID

    # Copy host script to stable location
    HOST_DIR.mkdir(parents=True, exist_ok=True)
    src_script = _REPO_BROWSER_DIR / "aad_browser_host.py"
    if not src_script.exists():
        return f"Error: host script not found at {src_script}"

    shutil.copy2(src_script, HOST_SCRIPT)
    HOST_SCRIPT.chmod(HOST_SCRIPT.stat().st_mode | stat.S_IEXEC)

    # Write Chrome NMH manifest
    CHROME_NMH_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": "com.eidos.aad.browser",
        "description": "apple-a-day browser activity logger",
        "path": str(HOST_SCRIPT),
        "type": "stdio",
        "allowed_origins": [f"chrome-extension://{ext_id}/"],
    }
    manifest_path = CHROME_NMH_DIR / MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    return (
        f"Installed:\n"
        f"  Host script: {HOST_SCRIPT}\n"
        f"  Chrome manifest: {manifest_path}\n"
        f"  Extension ID: {ext_id}\n"
        f"\nReload the extension in Chrome to connect."
    )


def uninstall() -> str:
    """Remove the native messaging host."""
    removed = []

    manifest_path = CHROME_NMH_DIR / MANIFEST_NAME
    if manifest_path.exists():
        manifest_path.unlink()
        removed.append(f"  Chrome manifest: {manifest_path}")

    if HOST_SCRIPT.exists():
        HOST_SCRIPT.unlink()
        removed.append(f"  Host script: {HOST_SCRIPT}")

    # Clean up empty dir
    if HOST_DIR.exists() and not any(HOST_DIR.iterdir()):
        HOST_DIR.rmdir()

    if removed:
        return "Removed:\n" + "\n".join(removed)
    return "Nothing to remove — native host was not installed."


def status() -> str:
    """Check native messaging host installation status."""
    manifest_path = CHROME_NMH_DIR / MANIFEST_NAME
    lines = []

    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        lines.append(f"Chrome manifest: {manifest_path}")
        lines.append(f"  Host path: {manifest.get('path', '?')}")
        origins = manifest.get("allowed_origins", [])
        ext_id = origins[0].replace("chrome-extension://", "").rstrip("/") if origins else "?"
        lines.append(f"  Extension ID: {ext_id}")

        host_path = Path(manifest.get("path", ""))
        if host_path.exists():
            lines.append(f"  Host script: exists, executable={bool(host_path.stat().st_mode & stat.S_IEXEC)}")
        else:
            lines.append(f"  Host script: MISSING at {host_path}")
    else:
        lines.append("Native host: not installed")
        lines.append("  Run: aad browser install")

    # Check for log file
    log_path = Path.home() / ".config" / "eidos" / "aad-logs" / "browser.ndjson"
    if log_path.exists():
        size_kb = log_path.stat().st_size / 1024
        lines.append(f"\nLog: {log_path} ({size_kb:.1f} KB)")
    else:
        lines.append(f"\nLog: no data yet ({log_path})")

    return "\n".join(lines)
