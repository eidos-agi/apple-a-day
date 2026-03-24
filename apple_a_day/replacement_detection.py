"""Detect app replacements by temporal usage patterns.

Instead of asking "are these apps similar?", asks "did one replace the other?"

Signal: App A went dormant around the time App B became active.
Filter: Lightweight metadata overlap (same category, same runtime, synonym group)
        prevents false positives like "you stopped using Pages when you installed Docker."

All data is local — Spotlight metadata + filesystem dates + Info.plist.
"""

import os
import subprocess
from datetime import datetime, timezone
from typing import NamedTuple

from .feature_extraction import extract_features


class AppUsage(NamedTuple):
    name: str
    path: str
    last_used: datetime | None  # kMDItemLastUsedDate
    use_count: int  # kMDItemUseCount
    date_added: datetime | None  # kMDItemDateAdded
    days_dormant: int  # days since last use (or since added if never used)
    size_mb: float


class Replacement(NamedTuple):
    stale: AppUsage
    replacement: AppUsage
    confidence: float  # 0-1
    reason: str


def get_app_usage(app_path: str) -> AppUsage | None:
    """Extract usage timeline from Spotlight metadata + filesystem."""
    name = os.path.basename(app_path).replace(".app", "")
    if not os.path.exists(app_path):
        return None

    md = _mdls(app_path)
    now = datetime.now(timezone.utc)

    last_used = _parse_date(md.get("kMDItemLastUsedDate"))
    use_count = int(md.get("kMDItemUseCount", 0) or 0)
    date_added = _parse_date(md.get("kMDItemDateAdded"))

    # Fallback: if no Spotlight data, use filesystem dates
    if not date_added:
        try:
            stat = os.stat(app_path)
            date_added = datetime.fromtimestamp(stat.st_birthtime, tz=timezone.utc)
        except (OSError, AttributeError):
            pass

    # Calculate dormancy
    if last_used:
        days_dormant = (now - last_used).days
    elif date_added:
        # Never used (or Spotlight doesn't track it) — dormant since added
        days_dormant = (now - date_added).days
    else:
        days_dormant = 999

    # App size
    size_mb = 0.0
    try:
        total = sum(
            os.path.getsize(os.path.join(dirpath, f))
            for dirpath, _, filenames in os.walk(app_path)
            for f in filenames
        )
        size_mb = round(total / (1024 * 1024), 1)
    except (OSError, PermissionError):
        pass

    return AppUsage(
        name=name,
        path=app_path,
        last_used=last_used,
        use_count=use_count,
        date_added=date_added,
        days_dormant=days_dormant,
        size_mb=size_mb,
    )


def find_replacements(
    stale_days: int = 90,
    active_days: int = 30,
) -> list[Replacement]:
    """Find apps that were likely replaced by other installed apps.

    An app A is considered replaced by app B when:
    1. A is dormant (unused for >= stale_days)
    2. B is active (used within active_days)
    3. A and B share a lightweight signal (category, runtime, synonym group, or UTIs)
    4. Bonus confidence if B was added around when A went dormant
    """
    import glob

    # Gather usage data for all apps
    apps: list[tuple[AppUsage, dict]] = []
    for app_path in sorted(glob.glob("/Applications/*.app")):
        usage = get_app_usage(app_path)
        if usage is None:
            continue
        # Get lightweight metadata for filtering
        meta = _get_lightweight_meta(app_path)
        apps.append((usage, meta))

    # Split into stale and active
    stale = [(u, m) for u, m in apps if u.days_dormant >= stale_days]
    active = [(u, m) for u, m in apps if u.days_dormant < active_days and u.use_count > 0]

    replacements: list[Replacement] = []

    for stale_usage, stale_meta in stale:
        best: Replacement | None = None
        best_conf = 0.0

        for active_usage, active_meta in active:
            if stale_usage.name == active_usage.name:
                continue

            # Check for overlap signals
            signals = _overlap_signals(
                stale_usage,
                stale_meta,
                active_usage,
                active_meta,
            )

            if not signals:
                continue  # No evidence these apps are related

            # Calculate confidence
            confidence = _calculate_confidence(stale_usage, active_usage, signals)

            if confidence > best_conf and confidence >= 0.3:
                reason = ". ".join(signals)
                best = Replacement(
                    stale=stale_usage,
                    replacement=active_usage,
                    confidence=round(confidence, 2),
                    reason=reason,
                )
                best_conf = confidence

        if best is not None:
            replacements.append(best)

    replacements.sort(key=lambda r: r.confidence, reverse=True)
    return replacements


def _overlap_signals(
    stale_usage: AppUsage,
    stale_meta: dict,
    active_usage: AppUsage,
    active_meta: dict,
) -> list[str]:
    """Check if two apps have enough in common to be potential replacements."""
    signals = []

    # 1. Synonym group (strongest signal)
    from .app_similarity import _known_synonym_score

    if _known_synonym_score(stale_usage.name, active_usage.name) > 0:
        signals.append("known competitors")

    # 2. Same category (medium signal, skip broad categories)
    cat_a = stale_meta.get("category", "")
    cat_b = active_meta.get("category", "")
    broad = {
        "public.app-category.utilities",
        "public.app-category.productivity",
        "public.app-category.business",
    }
    if cat_a and cat_b and cat_a == cat_b and cat_a not in broad:
        label = cat_a.replace("public.app-category.", "").replace("-", " ")
        signals.append(f"both in '{label}' category")

    # 3. Same runtime (weak but useful as supporting evidence)
    rt_a = stale_meta.get("runtime", "unknown")
    rt_b = active_meta.get("runtime", "unknown")
    if rt_a == rt_b and rt_a not in ("unknown", "native"):
        signals.append(f"both {rt_a} apps")

    # 4. Shared UTIs (medium signal)
    utis_a = stale_meta.get("utis", set())
    utis_b = active_meta.get("utis", set())
    generic = {
        "public.data",
        "public.item",
        "public.content",
        "public.text",
        "public.plain-text",
        "public.image",
        "public.movie",
    }
    shared = (utis_a & utis_b) - generic
    if shared:
        types = [t.split(".")[-1] for t in sorted(shared)[:3]]
        signals.append(f"shared file types: {', '.join(types)}")

    # 5. Same vendor (medium signal)
    vendor_a = stale_meta.get("vendor", "")
    vendor_b = active_meta.get("vendor", "")
    if vendor_a and vendor_b and vendor_a == vendor_b and vendor_a != "com.apple":
        signals.append(f"same developer ({vendor_a})")

    return signals


def _calculate_confidence(
    stale: AppUsage,
    active: AppUsage,
    signals: list[str],
) -> float:
    """Score how confident we are that active replaced stale."""
    conf = 0.0

    # Signal strength
    if "known competitors" in signals:
        conf += 0.5
    for s in signals:
        if "category" in s:
            conf += 0.2
        elif "file types" in s:
            conf += 0.15
        elif "same developer" in s:
            conf += 0.1
        elif "both" in s and "apps" in s:  # runtime match
            conf += 0.05

    # Temporal bonus: did the replacement arrive around when the stale app went dormant?
    if stale.last_used and active.date_added:
        gap_days = abs((active.date_added - stale.last_used).days)
        if gap_days < 30:
            conf += 0.2  # Strong temporal signal
        elif gap_days < 90:
            conf += 0.1  # Moderate temporal signal

    # Usage volume: if the stale app was heavily used, replacement is more meaningful
    if stale.use_count > 20:
        conf += 0.05

    # Size reclaim bonus: bigger stale app = more reason to flag
    if stale.size_mb > 500:
        conf += 0.05

    return min(conf, 1.0)


def _get_lightweight_meta(app_path: str) -> dict:
    """Get just the metadata needed for overlap filtering (fast)."""
    import plistlib

    result: dict = {"category": "", "utis": set(), "runtime": "unknown", "vendor": ""}

    plist_path = os.path.join(app_path, "Contents", "Info.plist")
    if os.path.exists(plist_path):
        try:
            with open(plist_path, "rb") as f:
                info = plistlib.load(f)
            result["category"] = info.get("LSApplicationCategoryType", "")
            result["vendor"] = ".".join(info.get("CFBundleIdentifier", "").split(".")[:2])
            utis = set()
            for dt in info.get("CFBundleDocumentTypes", []):
                for uti in dt.get("LSItemContentTypes", []):
                    utis.add(uti)
            result["utis"] = utis
        except Exception:
            pass

    features = extract_features(app_path)
    result["runtime"] = features.get("runtime", "unknown")
    return result


def _mdls(app_path: str) -> dict:
    """Query Spotlight metadata for an app."""
    fields = [
        "kMDItemLastUsedDate",
        "kMDItemUseCount",
        "kMDItemDateAdded",
        "kMDItemContentCreationDate",
    ]
    result = {}
    try:
        args = ["mdls"]
        for f in fields:
            args.extend(["-name", f])
        args.append(app_path)
        out = subprocess.run(args, capture_output=True, text=True, timeout=10)
        if out.returncode == 0:
            for line in out.stdout.strip().split("\n"):
                if " = " in line and "(null)" not in line:
                    key, val = line.split(" = ", 1)
                    result[key.strip()] = val.strip().strip('"')
    except (subprocess.TimeoutExpired, OSError):
        pass
    return result


def _parse_date(val: str | None) -> datetime | None:
    """Parse Spotlight date string to datetime."""
    if not val:
        return None
    try:
        # Format: "2026-03-24 05:39:37 +0000"
        return datetime.strptime(val, "%Y-%m-%d %H:%M:%S %z")
    except (ValueError, TypeError):
        return None
