"""Mac user profiling — shared between apple-a-day and space-hog.

First pass: gather signals from the Mac (installed tools, directory sizes, shell history, etc.)
Second pass: an agent reviews the profile to classify user type and tailor recommendations.

Profile is stored at ~/.config/eidos/mac-profile.json and shared across tools.
"""

import json
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path


PROFILE_DIR = Path.home() / ".config" / "eidos"
PROFILE_PATH = PROFILE_DIR / "mac-profile.json"


def _count_history_commands(top_n: int = 30) -> list[dict]:
    """Top N commands from shell history."""
    history_file = Path.home() / ".zsh_history"
    if not history_file.exists():
        history_file = Path.home() / ".bash_history"
    if not history_file.exists():
        return []

    commands = Counter()
    try:
        with open(history_file, "rb") as f:
            for line in f.readlines()[-50000:]:
                try:
                    text = line.decode("utf-8", errors="ignore").strip()
                    if text.startswith(":"):
                        text = text.split(";", 1)[-1] if ";" in text else text
                    cmd = text.split()[0].rsplit("/", 1)[-1] if text else ""
                    if cmd and not cmd.startswith("#"):
                        commands[cmd] += 1
                except (IndexError, UnicodeDecodeError):
                    continue
    except OSError:
        pass

    return [{"command": cmd, "count": count} for cmd, count in commands.most_common(top_n)]


def _detect_dev_tools() -> dict:
    """Detect installed development tools and languages."""
    tools = {}

    checks = {
        "python": ["python3", "--version"],
        "node": ["node", "--version"],
        "rust": ["rustc", "--version"],
        "go": ["go", "version"],
        "java": ["java", "--version"],
        "ruby": ["ruby", "--version"],
        "swift": ["swift", "--version"],
        "docker": ["docker", "--version"],
        "brew": ["brew", "--version"],
        "git": ["git", "--version"],
        "claude": ["claude", "--version"],
        "gh": ["gh", "--version"],
        "terraform": ["terraform", "--version"],
        "kubectl": ["kubectl", "version", "--client"],
        "aws": ["aws", "--version"],
        "supabase": ["supabase", "--version"],
        "railway": ["railway", "--version"],
    }

    for name, cmd in checks.items():
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if out.returncode == 0:
                version = (out.stdout + out.stderr).strip().split("\n")[0][:80]
                tools[name] = version
        except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
            pass

    return tools


def _detect_editors() -> list[str]:
    """Detect installed code editors and IDEs."""
    editors = []
    checks = {
        "VS Code": "/Applications/Visual Studio Code.app",
        "Cursor": "/Applications/Cursor.app",
        "Xcode": "/Applications/Xcode.app",
        "IntelliJ IDEA": "/Applications/IntelliJ IDEA.app",
        "PyCharm": "/Applications/PyCharm.app",
        "Sublime Text": "/Applications/Sublime Text.app",
        "Vim/Neovim": None,  # check binary
        "Emacs": None,
    }

    for name, path in checks.items():
        if path and Path(path).exists():
            editors.append(name)
        elif name == "Vim/Neovim":
            try:
                subprocess.run(["nvim", "--version"], capture_output=True, timeout=3)
                editors.append("Neovim")
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

    return editors


def _detect_workspace_shape() -> dict:
    """Analyze the shape of the user's workspace."""
    home = Path.home()
    shape = {
        "repo_count": 0,
        "repo_dirs": [],
        "has_docker": Path("/Applications/Docker.app").exists(),
        "has_xcode": Path("/Applications/Xcode.app").exists(),
    }

    # Count repos
    for repos_dir in [
        home / "repos",
        home / "repos-eidos-agi",
        home / "repos-aic",
        home / "Projects",
        home / "Developer",
        home / "code",
        home / "src",
    ]:
        if repos_dir.exists():
            count = sum(1 for d in repos_dir.iterdir() if d.is_dir() and (d / ".git").exists())
            if count > 0:
                shape["repo_dirs"].append({"path": str(repos_dir), "count": count})
                shape["repo_count"] += count

    # Detect languages from repos (sample first 20 repos)
    lang_signals = Counter()
    repo_paths = []
    for rd in shape["repo_dirs"]:
        for d in Path(rd["path"]).iterdir():
            if d.is_dir() and (d / ".git").exists():
                repo_paths.append(d)
                if len(repo_paths) >= 20:
                    break

    for repo in repo_paths[:20]:
        if (repo / "package.json").exists():
            lang_signals["javascript/typescript"] += 1
        if (repo / "pyproject.toml").exists() or (repo / "setup.py").exists():
            lang_signals["python"] += 1
        if (repo / "Cargo.toml").exists():
            lang_signals["rust"] += 1
        if (repo / "go.mod").exists():
            lang_signals["go"] += 1
        if (repo / "Gemfile").exists():
            lang_signals["ruby"] += 1
        if any(repo.glob("*.xcodeproj")) or any(repo.glob("*.xcworkspace")):
            lang_signals["swift/objc"] += 1

    shape["languages"] = dict(lang_signals.most_common())

    return shape


def _get_hardware() -> dict:
    """Get hardware profile."""
    import platform

    hw = {
        "os_version": platform.mac_ver()[0],
        "arch": platform.machine(),
    }

    for key, cmd in [
        ("cpu", ["sysctl", "-n", "machdep.cpu.brand_string"]),
        ("memory_gb", ["sysctl", "-n", "hw.memsize"]),
        ("model", ["sysctl", "-n", "hw.model"]),
    ]:
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            val = out.stdout.strip()
            if key == "memory_gb":
                val = round(int(val) / (1024**3))
            hw[key] = val
        except (subprocess.TimeoutExpired, OSError, ValueError):
            pass

    # Disk size
    try:
        out = subprocess.run(["diskutil", "info", "/"], capture_output=True, text=True, timeout=10)
        for line in out.stdout.split("\n"):
            if "Disk Size" in line and "Bytes" in line:
                b = int(line.split("(")[1].split(" Bytes")[0])
                hw["disk_gb"] = round(b / (1000**3))
                break
    except (subprocess.TimeoutExpired, OSError, ValueError, IndexError):
        pass

    return hw


def gather_profile() -> dict:
    """Gather all signals into a raw profile. Takes ~5-10 seconds."""
    return {
        "version": 1,
        "gathered_at": datetime.now().isoformat(),
        "hardware": _get_hardware(),
        "dev_tools": _detect_dev_tools(),
        "editors": _detect_editors(),
        "workspace": _detect_workspace_shape(),
        "top_commands": _count_history_commands(30),
        "user_type": None,  # filled by classify_user()
        "tags": [],  # filled by classify_user()
    }


def classify_user(profile: dict) -> dict:
    """Classify user type from gathered signals. Returns updated profile."""
    tags = set()
    tools = profile.get("dev_tools", {})
    workspace = profile.get("workspace", {})
    langs = workspace.get("languages", {})
    top_cmds = {c["command"]: c["count"] for c in profile.get("top_commands", [])}

    # Language expertise
    if langs.get("python", 0) >= 3 or "python" in tools:
        tags.add("python-dev")
    if langs.get("javascript/typescript", 0) >= 3 or "node" in tools:
        tags.add("js-dev")
    if langs.get("rust", 0) >= 1 or "rust" in tools:
        tags.add("rust-dev")
    if langs.get("go", 0) >= 1 or "go" in tools:
        tags.add("go-dev")
    if langs.get("swift/objc", 0) >= 1 or workspace.get("has_xcode"):
        tags.add("ios-dev")

    # Infrastructure
    if any(t in tools for t in ["terraform", "kubectl", "aws"]):
        tags.add("infra-ops")
    if "docker" in tools or workspace.get("has_docker"):
        tags.add("docker-user")
    if any(t in tools for t in ["railway", "supabase"]):
        tags.add("paas-user")

    # AI/Agent work
    if "claude" in tools or top_cmds.get("claude", 0) > 10:
        tags.add("ai-agent-user")
    if any(t in tools for t in ["ollama"]):
        tags.add("local-llm-user")

    # Repo scale
    repo_count = workspace.get("repo_count", 0)
    if repo_count >= 20:
        tags.add("heavy-developer")
    elif repo_count >= 5:
        tags.add("active-developer")

    # Determine primary user type
    if "heavy-developer" in tags and "ai-agent-user" in tags:
        user_type = "ai-native developer"
    elif "heavy-developer" in tags:
        user_type = "professional developer"
    elif "active-developer" in tags:
        user_type = "developer"
    elif "infra-ops" in tags:
        user_type = "devops/sre"
    elif "ios-dev" in tags:
        user_type = "ios developer"
    else:
        user_type = "power user"

    profile["user_type"] = user_type
    profile["tags"] = sorted(tags)

    return profile


def load_profile() -> dict | None:
    """Load existing profile from disk."""
    if PROFILE_PATH.exists():
        try:
            return json.loads(PROFILE_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            return None
    return None


def save_profile(profile: dict) -> Path:
    """Save profile to shared location."""
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.write_text(json.dumps(profile, indent=2))
    return PROFILE_PATH


def get_or_create_profile(force_refresh: bool = False) -> dict:
    """Load existing profile or create one. Refreshes if older than 7 days."""
    if not force_refresh:
        existing = load_profile()
        if existing:
            gathered = existing.get("gathered_at", "")
            try:
                age_days = (datetime.now() - datetime.fromisoformat(gathered)).days
                if age_days < 90:
                    return existing
            except (ValueError, TypeError):
                pass

    profile = gather_profile()
    profile = classify_user(profile)
    save_profile(profile)
    return profile
