"""Suggest apps, launch agents, and login items to uninstall or disable.

Scoring heuristic (from ChatGPT research):
  K = 0.6 * usage_freq + 0.4 * (1 - recency)   # how "loved" it is
  A = 0.4 * mem + 0.4 * cpu + 0.2 * auto_start  # how "costly" it is
  C = A + 0.5 * redundancy - K                   # candidate score

High C = good uninstall/disable candidate.

Data sources:
  - mdls kMDItemLastUsedDate for app recency
  - launchctl list + LaunchAgent plists for startup items
  - ps for current CPU/memory footprint
  - Bundle ID mapping to link apps ↔ agents
"""

import glob
import os
import plistlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from ..models import CheckResult, Finding, Severity

# Apps that should never be suggested for removal
_SAFE_BUNDLE_PREFIXES = ("com.apple.", "com.microsoft.Office", "com.google.Chrome")
_SAFE_APPS = {
    "Safari", "Finder", "System Settings", "System Preferences",
    "App Store", "Terminal", "Console", "Activity Monitor",
    "Disk Utility", "Migration Assistant", "Boot Camp Assistant",
    "Font Book", "Keychain Access", "Screenshot", "Preview",
    "TextEdit", "Calculator", "Music", "Photos", "Maps",
    "Messages", "FaceTime", "Mail", "Calendar", "Contacts",
    "Notes", "Reminders", "Freeform", "Shortcuts", "Clock",
    "Home", "Stocks", "Weather", "News", "Podcasts", "TV",
    "Books", "Voice Memos", "QuickTime Player",
}


def check_cleanup() -> CheckResult:
    """Find apps and services that are candidates for removal or disabling."""
    result = CheckResult(name="Cleanup")

    stale_apps = _find_stale_apps()
    orphaned_agents = _find_orphaned_agents()
    crash_looping = _find_crash_looping_agents()

    # --- Stale apps ---
    if stale_apps:
        strong = [a for a in stale_apps if a["score"] >= 0.25]
        moderate = [a for a in stale_apps if 0.1 < a["score"] < 0.25]

        if strong:
            names = [a["name"] for a in strong[:8]]
            details = "\n".join(
                f"  {a['name']:35s} last used: {a['last_used'] or 'never':20s} score: {a['score']:.2f}"
                for a in strong[:8]
            )
            result.findings.append(Finding(
                check="cleanup",
                severity=Severity.INFO,
                summary=f"{len(strong)} app(s) not used in 90+ days: {', '.join(names[:5])}{'...' if len(names) > 5 else ''}",
                details=details,
                fix="Review and uninstall unused apps. Drag to Trash or use `sudo rm -rf /Applications/<App>.app`",
            ))

        if moderate:
            names = [a["name"] for a in moderate[:5]]
            result.findings.append(Finding(
                check="cleanup",
                severity=Severity.INFO,
                summary=f"{len(moderate)} app(s) rarely used: {', '.join(names[:5])}",
                details="\n".join(
                    f"  {a['name']:35s} last used: {a['last_used'] or 'never':20s} score: {a['score']:.2f}"
                    for a in moderate[:5]
                ),
            ))

    # --- Orphaned launch agents ---
    if orphaned_agents:
        details = "\n".join(f"  {a['label']:50s} → {a['reason']}" for a in orphaned_agents[:10])
        result.findings.append(Finding(
            check="cleanup",
            severity=Severity.WARNING,
            summary=f"{len(orphaned_agents)} orphaned launch agent(s) — app removed but agent persists",
            details=details,
            fix="Remove orphaned plists: `launchctl bootout gui/$(id -u) <plist_path>` then delete the file",
        ))

    # --- Crash-looping agents (high annoyance, should disable) ---
    if crash_looping:
        details = "\n".join(
            f"  {a['label']:50s} exit={a['exit_code']}  restarts={a['restarts']}"
            for a in crash_looping[:5]
        )
        result.findings.append(Finding(
            check="cleanup",
            severity=Severity.WARNING,
            summary=f"{len(crash_looping)} launch agent(s) stuck in crash loops — wasting CPU",
            details=details,
            fix="Disable with: `launchctl bootout gui/$(id -u) <plist_path>` — fix or remove the underlying app",
        ))

    if not result.findings:
        result.findings.append(Finding(
            check="cleanup",
            severity=Severity.OK,
            summary="No obvious cleanup candidates found",
        ))

    return result


def _find_stale_apps() -> list[dict]:
    """Find apps not used recently, scored by staleness + resource cost."""
    apps = glob.glob("/Applications/*.app") + glob.glob(
        os.path.expanduser("~/Applications/*.app")
    )

    now = datetime.now(timezone.utc)
    scored = []

    # Get current process resource usage for mapping
    proc_cpu = _get_process_cpu_map()

    for app_path in apps:
        name = os.path.basename(app_path).replace(".app", "")

        # Skip Apple and safe apps
        if name in _SAFE_APPS:
            continue
        bundle_id = _get_bundle_id(app_path)
        if bundle_id and any(bundle_id.startswith(p) for p in _SAFE_BUNDLE_PREFIXES):
            continue

        # Recency: days since last used
        last_used_str = _get_last_used(app_path)
        if last_used_str:
            try:
                last_dt = datetime.fromisoformat(last_used_str.replace(" +0000", "+00:00"))
                days_ago = (now - last_dt).days
            except ValueError:
                days_ago = 999
        else:
            days_ago = 999  # never used / unknown

        # Get app size
        try:
            size_bytes = sum(
                f.stat().st_size for f in Path(app_path).rglob("*") if f.is_file()
            ) if os.path.isdir(app_path) else 0
        except (OSError, PermissionError):
            size_bytes = 0
        size_mb = round(size_bytes / (1024 * 1024))

        # Skip if used in the last 30 days
        if days_ago < 30:
            continue

        # Recency score R: 0 (just used) to 1 (very stale)
        r = min(days_ago / 365.0, 1.0)

        # Usage frequency U: 0 if not used recently, basic heuristic
        u = max(0, 1.0 - (days_ago / 180.0))

        # Auto-start S: check if it has a login item or launch agent
        has_agent = _app_has_agent(bundle_id) if bundle_id else False
        s = 1.0 if has_agent else 0.0

        # CPU/mem from current processes (if running)
        cpu_pct = proc_cpu.get(name.lower(), 0)
        p = min(cpu_pct / 100.0, 1.0)

        # Keep score and annoyance score
        k = 0.6 * u + 0.4 * (1 - r)
        a = 0.4 * 0 + 0.4 * p + 0.2 * s  # mem=0 for now (not sampling)

        # Candidate score
        c = a - k + 0.3 * r  # boost stale apps

        if c > 0.1:
            scored.append({
                "name": name,
                "path": app_path,
                "bundle_id": bundle_id,
                "last_used": f"{days_ago}d ago" if days_ago < 999 else "never",
                "days_ago": days_ago,
                "has_agent": has_agent,
                "size_mb": size_mb,
                "score": round(c, 3),
            })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


def _find_orphaned_agents() -> list[dict]:
    """Find LaunchAgents whose parent app is no longer installed."""
    orphaned = []
    agent_dir = Path.home() / "Library" / "LaunchAgents"

    if not agent_dir.exists():
        return orphaned

    installed_bundles = set()
    for app_path in glob.glob("/Applications/*.app") + glob.glob(
        os.path.expanduser("~/Applications/*.app")
    ):
        bid = _get_bundle_id(app_path)
        if bid:
            installed_bundles.add(bid)

    for plist_path in agent_dir.glob("*.plist"):
        if plist_path.name == "_disabled":
            continue

        label = plist_path.stem
        # Skip Apple and our own agents
        if label.startswith("com.apple."):
            continue

        try:
            with open(plist_path, "rb") as f:
                plist = plistlib.load(f)
        except Exception:
            continue

        prog_args = plist.get("ProgramArguments", [])
        program = plist.get("Program", "")
        all_paths = prog_args + ([program] if program else [])

        # Check if the binary/script exists
        binary_missing = False
        for p in all_paths:
            if p.startswith("/") and not os.path.exists(p):
                binary_missing = True
                orphaned.append({
                    "label": label,
                    "plist": str(plist_path),
                    "reason": f"binary missing: {p}",
                })
                break

        if binary_missing:
            continue

        # Check if it references an app bundle that's not installed
        # Extract bundle ID from label as heuristic
        parts = label.split(".")
        if len(parts) >= 3:
            possible_bundle = ".".join(parts[:3])
            # Only flag if it looks like it belongs to a third-party app
            # and that app is not installed
            if (not possible_bundle.startswith("com.apple.")
                    and not possible_bundle.startswith("homebrew.")
                    and possible_bundle not in installed_bundles):
                # Check if the program path references an uninstalled app
                for p in all_paths:
                    if "/Applications/" in p:
                        app_ref = p.split("/Applications/")[1].split("/")[0]
                        if not os.path.exists(f"/Applications/{app_ref}"):
                            orphaned.append({
                                "label": label,
                                "plist": str(plist_path),
                                "reason": f"app uninstalled: {app_ref}",
                            })
                            break

    return orphaned


def _find_crash_looping_agents() -> list[dict]:
    """Find LaunchAgents that are crash-looping (non-zero exit + KeepAlive)."""
    looping = []

    try:
        out = subprocess.run(
            ["launchctl", "list"],
            capture_output=True, text=True, timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError):
        return looping

    for line in out.stdout.strip().split("\n")[1:]:  # skip header
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        pid, status, label = parts

        # Skip Apple daemons
        if label.startswith("com.apple."):
            continue

        # Non-zero exit and no running PID = likely crash-looping
        if pid == "-" and status not in ("0", ""):
            try:
                exit_code = int(status)
            except ValueError:
                continue

            # Check if it has KeepAlive in its plist
            plist_path = Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"
            if not plist_path.exists():
                continue

            try:
                with open(plist_path, "rb") as f:
                    plist = plistlib.load(f)
            except Exception:
                continue

            keep_alive = plist.get("KeepAlive", False)
            if keep_alive is True or (isinstance(keep_alive, dict) and keep_alive.get("SuccessfulExit") is False):
                looping.append({
                    "label": label,
                    "exit_code": exit_code,
                    "plist": str(plist_path),
                    "restarts": "continuous",
                })

    return looping


def _get_last_used(app_path: str) -> str | None:
    """Get kMDItemLastUsedDate from Spotlight metadata."""
    try:
        out = subprocess.run(
            ["mdls", "-name", "kMDItemLastUsedDate", "-raw", app_path],
            capture_output=True, text=True, timeout=5,
        )
        val = out.stdout.strip()
        return val if val and val != "(null)" else None
    except (subprocess.TimeoutExpired, OSError):
        return None


def _get_bundle_id(app_path: str) -> str | None:
    """Read CFBundleIdentifier from app's Info.plist."""
    plist_path = os.path.join(app_path, "Contents", "Info.plist")
    if not os.path.exists(plist_path):
        return None
    try:
        with open(plist_path, "rb") as f:
            info = plistlib.load(f)
        return info.get("CFBundleIdentifier")
    except Exception:
        return None


def _app_has_agent(bundle_id: str) -> bool:
    """Check if an app has a LaunchAgent or login item."""
    agent_dir = Path.home() / "Library" / "LaunchAgents"
    if agent_dir.exists():
        # Check by bundle ID prefix in agent labels
        prefix = bundle_id.lower()
        for plist in agent_dir.glob("*.plist"):
            if plist.stem.lower().startswith(prefix):
                return True
    return False


def _get_process_cpu_map() -> dict[str, float]:
    """Get current CPU usage by process name (lowercase)."""
    try:
        out = subprocess.run(
            ["ps", "-eo", "pcpu,comm"],
            capture_output=True, text=True, timeout=5,
        )
        cpu_map: dict[str, float] = {}
        for line in out.stdout.strip().split("\n")[1:]:
            parts = line.strip().split(None, 1)
            if len(parts) == 2:
                cpu = float(parts[0])
                name = parts[1].rsplit("/", 1)[-1].lower()
                cpu_map[name] = cpu_map.get(name, 0) + cpu
        return cpu_map
    except (subprocess.TimeoutExpired, OSError):
        return {}
