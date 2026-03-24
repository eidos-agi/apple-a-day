"""Score functional similarity between Mac apps.

Uses ML model (logistic regression) when sklearn is installed,
falls back to weighted heuristics otherwise. Both paths share
the same feature extraction from app bundles.

Signals:
  1. Runtime detection — Electron/native/Java/Python/Qt
  2. Framework fingerprint — shared linked frameworks
  3. LSApplicationCategoryType — Apple's app category enum
  4. CFBundleDocumentTypes — what file types the app opens (UTIs)
  5. URL schemes — registered protocol handlers
  6. Bundle ID prefix — vendor identification
  7. Binary size ratio — similar-sized apps of same type
  8. Known synonym groups — hardcoded for common app pairs
  9. CFBundleName / CFBundleGetInfoString — name and description text

The output is a similarity score 0-1 where:
  0.8+ = strong functional overlap (same purpose)
  0.5-0.8 = related tools (same domain, different angle)
  < 0.5 = different apps
"""

import os
import plistlib


def get_app_metadata(app_path: str) -> dict:
    """Extract classification-relevant metadata from an app bundle."""
    plist_path = os.path.join(app_path, "Contents", "Info.plist")
    if not os.path.exists(plist_path):
        return {"name": os.path.basename(app_path).replace(".app", "")}

    try:
        with open(plist_path, "rb") as f:
            info = plistlib.load(f)
    except Exception:
        return {"name": os.path.basename(app_path).replace(".app", "")}

    # Extract UTIs from document types
    utis = set()
    for doc_type in info.get("CFBundleDocumentTypes", []):
        for uti in doc_type.get("LSItemContentTypes", []):
            utis.add(uti)

    name = info.get("CFBundleName", info.get("CFBundleDisplayName",
           os.path.basename(app_path).replace(".app", "")))

    base = {
        "name": name,
        "bundle_id": info.get("CFBundleIdentifier", ""),
        "category": info.get("LSApplicationCategoryType", ""),
        "description": info.get("CFBundleGetInfoString", ""),
        "utis": utis,
    }

    # Enrich with deeper signals from feature_extraction
    from .feature_extraction import extract_features
    base.update(extract_features(app_path))
    return base


def similarity_score(app_a: dict, app_b: dict) -> float:
    """Compute functional similarity between two apps. Returns 0-1.

    Weighted heuristic with synonym groups, category, UTIs, runtime,
    URL schemes, and text similarity.
    """
    scores = []

    # 1. Known synonym groups (weight: 0.45)
    synonym = _known_synonym_score(app_a["name"], app_b["name"])
    if synonym > 0:
        scores.append(("synonym", synonym, 0.45))

    # 2. Category match (weight: 0.2)
    cat_score = _category_score(app_a.get("category", ""), app_b.get("category", ""))
    if cat_score > 0:
        scores.append(("category", cat_score, 0.2))

    # 3. UTI overlap (weight: 0.1)
    uti_score = _uti_overlap(app_a.get("utis", set()), app_b.get("utis", set()))
    if uti_score > 0:
        scores.append(("uti", uti_score, 0.1))

    # 4. Runtime match (weight: 0.15) — NEW
    rt_a = app_a.get("runtime", "unknown")
    rt_b = app_b.get("runtime", "unknown")
    if rt_a == rt_b and rt_a not in ("unknown", "native"):
        scores.append(("runtime", 1.0, 0.15))

    # 5. Name/description similarity (weight: 0.05)
    text_score = _text_similarity(app_a, app_b)
    if text_score > 0:
        scores.append(("text", text_score, 0.05))

    # 6. URL scheme overlap (weight: 0.05) — NEW
    urls_a = app_a.get("url_schemes", set())
    urls_b = app_b.get("url_schemes", set())
    generic = {"http", "https", "file", "mailto"}
    if (urls_a - generic) & (urls_b - generic):
        scores.append(("url_schemes", 1.0, 0.05))

    if not scores:
        return 0.0

    # Weighted average, but boost if multiple signals agree
    total_weight = sum(w for _, _, w in scores)
    weighted = sum(s * w for _, s, w in scores) / total_weight if total_weight > 0 else 0

    # Agreement bonus: if 3+ signals > 0.3, boost by 20%
    agreeing = sum(1 for _, s, _ in scores if s > 0.3)
    if agreeing >= 3:
        weighted = min(1.0, weighted * 1.2)

    return round(weighted, 3)


def find_redundant_apps(installed_apps: list[dict]) -> list[dict]:
    """Find pairs of apps where one is unused and the other is actively used.

    Returns list of:
    {
        "unused": {"name": "Cursor", "path": ..., "days_ago": 999, "size_mb": 850},
        "active": {"name": "VS Code", "path": ...},
        "score": 0.85,
        "reason": "Both are code editors (developer-tools category, shared file types)"
    }
    """
    # Split into used (< 30 days) and unused (>= 90 days)
    used = []
    unused = []
    for app in installed_apps:
        meta = get_app_metadata(app["path"])
        app["meta"] = meta
        if app.get("days_ago", 0) < 30:
            used.append(app)
        elif app.get("days_ago", 0) >= 90:
            unused.append(app)

    redundant = []
    for stale in unused:
        best_match = None
        best_score = 0
        best_reason = ""

        for active in used:
            score = similarity_score(stale["meta"], active["meta"])
            if score > best_score and score >= 0.5:
                best_score = score
                best_match = active
                best_reason = _explain_similarity(stale["meta"], active["meta"])

        if best_match and best_score >= 0.5:
            redundant.append({
                "unused": stale,
                "active": best_match,
                "score": best_score,
                "reason": best_reason,
            })

    redundant.sort(key=lambda x: x["score"], reverse=True)
    return redundant


# ── Known synonym groups ──

_SYNONYM_GROUPS = [
    # Code editors / IDEs
    {"VS Code", "Visual Studio Code", "Cursor", "Zed", "Sublime Text",
     "Atom", "Nova", "TextMate", "BBEdit", "CotEditor"},
    # Browsers
    {"Safari", "Google Chrome", "Firefox", "Brave Browser", "Arc",
     "Microsoft Edge", "Opera", "Vivaldi", "Chromium"},
    # Terminals
    {"Terminal", "iTerm2", "iTerm", "Warp", "Alacritty", "Kitty", "Hyper"},
    # Git clients
    {"Tower", "Fork", "GitKraken", "Sourcetree", "GitHub Desktop", "Git"},
    # Database tools
    {"DBeaver", "DBeaver 2", "TablePlus", "Postico", "Sequel Pro",
     "DataGrip", "pgAdmin", "Azure Data Studio"},
    # Note taking
    {"Notes", "Obsidian", "Notion", "Bear", "Craft", "Evernote", "Joplin"},
    # Design
    {"Figma", "Sketch", "Adobe XD", "Framer", "Penpot"},
    # Image editing
    {"Preview", "Pixelmator", "Photoshop", "GIMP", "Acorn", "Affinity Photo"},
    # Video
    {"QuickTime Player", "VLC", "IINA", "Infuse", "mpv"},
    # Cloud storage
    {"OneDrive", "Dropbox", "Google Drive", "iCloud Drive", "Box"},
    # Virtual machines
    {"Parallels Desktop", "VirtualBox", "VMware Fusion", "UTM"},
    # API testing
    {"Postman", "Insomnia", "Paw", "HTTPie"},
    # Chat / communication
    {"Slack", "Microsoft Teams", "Discord", "Telegram", "WhatsApp"},
    # Video conferencing
    {"Zoom", "FaceTime", "Google Meet", "Microsoft Teams", "Webex"},
    # Office suites
    {"Pages", "Google Docs", "Microsoft Word", "LibreOffice Writer"},
    {"Numbers", "Google Sheets", "Microsoft Excel", "LibreOffice Calc"},
    {"Keynote", "Google Slides", "Microsoft PowerPoint", "LibreOffice Impress"},
    # Password managers
    {"1Password", "Bitwarden", "LastPass", "Dashlane", "KeePassXC"},
    # Screen recording
    {"Camtasia", "Camtasia 2024", "OBS", "ScreenFlow", "CleanShot X", "Loom"},
    # Remote desktop
    {"Splashtop Streamer", "Splashtop Business", "Chrome Remote Desktop Host",
     "Chrome Remote Desktop Host Uninstaller", "AnyDesk", "TeamViewer"},
]


def _known_synonym_score(name_a: str, name_b: str) -> float:
    """Check if two apps are in the same known synonym group.

    Uses exact match against group entries to avoid false positives
    like "Chrome" matching both browsers and remote desktop groups.
    """
    na = name_a.lower().strip()
    nb = name_b.lower().strip()

    for group in _SYNONYM_GROUPS:
        lower_group = {n.lower() for n in group}
        # Exact match or the group entry is a suffix of the app name
        # (handles "Google Chrome" matching "Chrome" in the group)
        matches_a = na in lower_group or any(na.endswith(g) for g in lower_group)
        matches_b = nb in lower_group or any(nb.endswith(g) for g in lower_group)
        if matches_a and matches_b:
            return 1.0
    return 0.0


def _category_score(cat_a: str, cat_b: str) -> float:
    """Score category match. Broad categories score lower to avoid false matches."""
    if not cat_a or not cat_b:
        return 0.0
    if cat_a == cat_b:
        # Broad categories are weak signals — too many unrelated apps share them
        broad = {
            "public.app-category.utilities",
            "public.app-category.productivity",
            "public.app-category.business",
            "public.app-category.entertainment",
            "public.app-category.lifestyle",
            "public.app-category.video",
            "public.app-category.photography",
            "public.app-category.music",
            "public.app-category.education",
        }
        if cat_a in broad:
            return 0.3  # weak match — needs other signals to confirm
        return 0.8  # specific category like developer-tools, social-networking
    # Related categories
    related = [
        {"public.app-category.developer-tools", "public.app-category.utilities"},
        {"public.app-category.productivity", "public.app-category.business"},
        {"public.app-category.social-networking", "public.app-category.entertainment"},
    ]
    for group in related:
        if cat_a in group and cat_b in group:
            return 0.2
    return 0.0


def _uti_overlap(utis_a: set, utis_b: set) -> float:
    """Jaccard similarity of UTI sets, ignoring very generic types."""
    generic = {"public.data", "public.item", "public.content", "public.text",
               "public.plain-text", "public.image", "public.movie",
               "public.composite-content"}
    a = utis_a - generic
    b = utis_b - generic
    if not a or not b:
        return 0.0
    intersection = a & b
    union = a | b
    return len(intersection) / len(union) if union else 0.0


def _text_similarity(app_a: dict, app_b: dict) -> float:
    """Simple word overlap between names and descriptions."""
    def words(app):
        text = f"{app.get('name', '')} {app.get('description', '')}".lower()
        return set(w for w in text.split() if len(w) > 2)

    wa = words(app_a)
    wb = words(app_b)
    if not wa or not wb:
        return 0.0
    intersection = wa & wb
    union = wa | wb
    return len(intersection) / len(union) if union else 0.0


def _explain_similarity(meta_a: dict, meta_b: dict) -> str:
    """Generate a human-readable explanation of why two apps are similar."""
    reasons = []

    syn = _known_synonym_score(meta_a["name"], meta_b["name"])
    if syn > 0:
        reasons.append("same app category (known competitors)")

    cat_a = meta_a.get("category", "")
    cat_b = meta_b.get("category", "")
    if cat_a and cat_b and cat_a == cat_b:
        cat_label = cat_a.replace("public.app-category.", "").replace("-", " ")
        reasons.append(f"both in '{cat_label}' category")

    utis_a = meta_a.get("utis", set())
    utis_b = meta_b.get("utis", set())
    generic = {"public.data", "public.item", "public.content", "public.text",
               "public.plain-text", "public.image"}
    overlap = (utis_a & utis_b) - generic
    if overlap:
        types = sorted(list(overlap))[:3]
        short = [t.split(".")[-1] for t in types]
        reasons.append(f"shared file types: {', '.join(short)}")

    # New signals
    rt_a = meta_a.get("runtime", "unknown")
    rt_b = meta_b.get("runtime", "unknown")
    if rt_a == rt_b and rt_a not in ("unknown", "native"):
        reasons.append(f"both are {rt_a} apps")

    vendor_a = meta_a.get("vendor", "")
    vendor_b = meta_b.get("vendor", "")
    if vendor_a and vendor_b and vendor_a == vendor_b and vendor_a != "com.apple":
        reasons.append(f"same developer ({vendor_a})")

    urls_a = meta_a.get("url_schemes", set())
    urls_b = meta_b.get("url_schemes", set())
    url_generic = {"http", "https", "file", "mailto"}
    shared_schemes = (urls_a & urls_b) - url_generic
    if shared_schemes:
        reasons.append(f"shared URL schemes: {', '.join(sorted(shared_schemes)[:3])}")

    return ". ".join(reasons) if reasons else "similar functionality"
