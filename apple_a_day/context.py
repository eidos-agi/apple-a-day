"""Profile-aware context for tailoring health check findings.

Loads the shared Eidos Mac profile and provides helpers that checks
use to adjust severity, fix suggestions, and explanations based on
who the user is.
"""

from .profile import load_profile


def get_context() -> dict:
    """Load profile and return a context dict checks can use."""
    profile = load_profile() or {}
    tags = set(profile.get("tags", []))
    user_type = profile.get("user_type", "unknown")
    hw = profile.get("hardware", {})

    return {
        "user_type": user_type,
        "tags": tags,
        "memory_gb": hw.get("memory_gb", 0),
        "has_profile": bool(profile),
        # Derived flags for common checks
        "is_developer": "active-developer" in tags or "heavy-developer" in tags,
        "is_docker_user": "docker-user" in tags,
        "is_ai_user": "ai-agent-user" in tags,
        "is_ios_dev": "ios-dev" in tags,
    }


def swap_thresholds(ctx: dict) -> tuple[float, float]:
    """Return (warning_mb, critical_mb) swap thresholds based on RAM.

    A 36 GB Mac hitting 8 GB swap is different from an 8 GB Mac hitting 8 GB swap.
    Scale thresholds to ~25% of RAM for warning, ~75% for critical.
    """
    ram_gb = ctx.get("memory_gb", 16)
    warning = ram_gb * 1024 * 0.25   # 25% of RAM
    critical = ram_gb * 1024 * 0.75  # 75% of RAM
    return (warning, critical)


def crash_loop_fix(label: str, plist_path: str, ctx: dict) -> str:
    """Generate a profile-aware fix for a crash-looping service."""
    base_fix = f"Stop with: `launchctl bootout gui/$(id -u) {plist_path}`"

    if ctx.get("is_ai_user"):
        # AI agent users: suggest investigating the root cause first
        return (f"Investigate first: check if this service is needed by your agent workflow.\n"
                f"{base_fix}\n"
                f"Or fix the underlying issue — agents may depend on this service indirectly.")

    return f"{base_fix}\nOr fix the underlying issue and restart."


def disk_context(free_gb: float, used_pct: int, ctx: dict) -> str:
    """Add context to disk findings based on profile."""
    notes = []

    if ctx.get("is_docker_user"):
        notes.append("Docker images/containers may be a major consumer — check `docker system df`")
    if ctx.get("is_ios_dev"):
        notes.append("Xcode simulators and archives can consume 20-50 GB — check DerivedData")
    if "heavy-developer" in ctx.get("tags", set()):
        notes.append(f"With {ctx.get('memory_gb', '?')} GB RAM and heavy dev workload, "
                     f"keep at least 50 GB free to avoid swap pressure")

    return ". ".join(notes) if notes else ""
