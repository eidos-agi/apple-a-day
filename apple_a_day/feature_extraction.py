"""Extract classification signals from macOS app bundles.

All functions use stdlib only (os, plistlib, subprocess, glob).
No external dependencies — these signals feed the ensemble
similarity scorer in app_similarity.py.
"""

import glob as _glob
import json
import os
import plistlib
import subprocess


# Frameworks that indicate a specific runtime
_RUNTIME_MARKERS = {
    "electron": {"Electron Framework", "Electron", "Electron Helper"},
    "java": {"JavaAppletPlugin", "libjvm", "JavaNativeFoundation"},
    "python": {"Python.framework", "Python", "libpython"},
    "qt": {"QtCore", "QtGui", "QtWidgets", "QtWebEngine"},
    "chromium": {"Chromium Embedded Framework"},
}

# Frameworks too common to be useful for similarity (everyone links these)
_GENERIC_FRAMEWORKS = {
    "AppKit", "Foundation", "CoreFoundation", "Security", "SystemConfiguration",
    "CoreServices", "CoreGraphics", "IOKit", "CFNetwork", "DiskArbitration",
    "libobjc", "libSystem", "libz", "libc++", "libsqlite3",
}


def extract_features(app_path: str) -> dict:
    """Extract all classification signals from an app bundle."""
    return {
        "runtime": detect_runtime(app_path),
        "frameworks": get_framework_fingerprint(app_path),
        "url_schemes": get_url_schemes(app_path),
        "vendor": get_bundle_id_prefix(app_path),
        "binary_size": get_binary_size(app_path),
        "brew_desc": get_brew_description(app_path),
        "ui_vocabulary": get_localization_vocabulary(app_path),
    }


def detect_runtime(app_path: str) -> str:
    """Detect the app's runtime by scanning Contents/Frameworks/."""
    frameworks = get_framework_fingerprint(app_path)
    if not frameworks:
        return "native"  # No embedded frameworks = likely native Swift/ObjC

    framework_names = {f.replace(".framework", "") for f in frameworks}

    for runtime, markers in _RUNTIME_MARKERS.items():
        if framework_names & markers:
            return runtime

    # Heuristic: if it has Swift stdlib frameworks, it's native Swift
    if any("Swift" in f for f in framework_names):
        return "native"

    return "unknown"


def get_framework_fingerprint(app_path: str) -> set[str]:
    """List framework basenames from Contents/Frameworks/."""
    frameworks_dir = os.path.join(app_path, "Contents", "Frameworks")
    if not os.path.isdir(frameworks_dir):
        return set()

    result = set()
    try:
        for entry in os.listdir(frameworks_dir):
            name = entry.replace(".framework", "").replace(".dylib", "")
            if name not in _GENERIC_FRAMEWORKS:
                result.add(name)
    except PermissionError:
        pass
    return result


def get_url_schemes(app_path: str) -> set[str]:
    """Extract registered URL schemes from Info.plist."""
    plist = _read_plist(app_path)
    if not plist:
        return set()

    schemes = set()
    for url_type in plist.get("CFBundleURLTypes", []):
        for scheme in url_type.get("CFBundleURLSchemes", []):
            schemes.add(scheme.lower())
    return schemes


def get_bundle_id_prefix(app_path: str) -> str:
    """Extract vendor prefix from bundle ID (first two components).

    e.g. 'com.microsoft.VSCode' -> 'com.microsoft'
    """
    plist = _read_plist(app_path)
    if not plist:
        return ""

    bundle_id = plist.get("CFBundleIdentifier", "")
    parts = bundle_id.split(".")
    if len(parts) >= 2:
        return ".".join(parts[:2])
    return bundle_id


def get_binary_size(app_path: str) -> int:
    """Get the size of the main executable in bytes."""
    plist = _read_plist(app_path)
    if not plist:
        return 0

    executable = plist.get("CFBundleExecutable", "")
    if not executable:
        return 0

    binary_path = os.path.join(app_path, "Contents", "MacOS", executable)
    try:
        return os.path.getsize(binary_path)
    except OSError:
        return 0


def get_brew_description(app_path: str) -> str:
    """Get Homebrew cask description for this app. Returns '' if not a cask."""
    name = os.path.basename(app_path).replace(".app", "")
    # Map common app names to cask tokens
    cask_token = _app_name_to_cask(name)
    if not cask_token:
        return ""
    try:
        out = subprocess.run(
            ["brew", "info", "--cask", "--json=v2", cask_token],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode == 0:
            data = json.loads(out.stdout)
            for cask in data.get("casks", []):
                return cask.get("desc", "") or ""
    except (subprocess.TimeoutExpired, OSError, json.JSONDecodeError):
        pass
    return ""


def get_localization_vocabulary(app_path: str) -> set[str]:
    """Extract UI vocabulary from localization .strings files.

    Works well for native apps (Pages, Safari, Excel).
    Returns empty set for Electron apps (they bundle text in JS).
    """
    resources = os.path.join(app_path, "Contents", "Resources")
    if not os.path.isdir(resources):
        return set()

    # Try English localizations first
    words: set[str] = set()
    for lproj in ["en.lproj", "English.lproj", "Base.lproj"]:
        lproj_path = os.path.join(resources, lproj)
        if not os.path.isdir(lproj_path):
            continue
        strings_files = _glob.glob(os.path.join(lproj_path, "*.strings"))
        for sf in strings_files[:30]:  # Cap to avoid slow scans
            words.update(_parse_strings_file(sf))
        if words:
            break  # Got data from this lproj, done

    return words


def _parse_strings_file(path: str) -> set[str]:
    """Parse a .strings file (binary plist or text format) into words."""
    words: set[str] = set()
    # Try binary plist first
    try:
        with open(path, "rb") as f:
            data = plistlib.load(f)
        for v in data.values():
            if isinstance(v, str):
                _extract_words(v, words)
        return words
    except Exception:
        pass
    # Fall back to text format
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line and '"' in line:
                    parts = line.split('"')
                    for p in parts:
                        _extract_words(p, words)
    except Exception:
        pass
    return words


def _extract_words(text: str, into: set[str]) -> None:
    """Extract meaningful words from a UI string."""
    for word in text.split():
        w = word.strip(".,;:!?()[]{}\"'").lower()
        if len(w) > 2 and w.isalpha():
            into.add(w)


# Common app name → brew cask token mappings
_CASK_OVERRIDES = {
    "Visual Studio Code": "visual-studio-code",
    "Google Chrome": "google-chrome",
    "Microsoft Excel": "microsoft-excel",
    "Microsoft Teams": "microsoft-teams",
    "DBeaver": "dbeaver-community",
    "DBeaver 2": "dbeaver-community",
    "Camtasia 2024": "camtasia",
    "Splashtop Business": "splashtop-business",
    "Splashtop Streamer": "splashtop-streamer",
    "Chrome Remote Desktop Host Uninstaller": "",  # Skip
    "Parallels Toolbox": "parallels-toolbox",
}


def _app_name_to_cask(name: str) -> str:
    """Convert an app display name to a Homebrew cask token."""
    if name in _CASK_OVERRIDES:
        return _CASK_OVERRIDES[name]
    # Default: lowercase, replace spaces with hyphens
    return name.lower().replace(" ", "-")


def _read_plist(app_path: str) -> dict | None:
    """Read Info.plist from an app bundle. Returns None on failure."""
    plist_path = os.path.join(app_path, "Contents", "Info.plist")
    if not os.path.exists(plist_path):
        return None
    try:
        with open(plist_path, "rb") as f:
            return plistlib.load(f)
    except Exception:
        return None
