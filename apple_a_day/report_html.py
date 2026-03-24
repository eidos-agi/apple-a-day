"""Render apple-a-day health report using Jinja2 templates.

Templates live in apple_a_day/templates/. This module collects data
and passes it to the templates — no HTML assembly here.
"""

import glob as _glob
import os
import subprocess
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from .app_similarity import find_redundant_apps
from .checks.cleanup import _find_stale_apps, _get_last_used, _SAFE_APPS
from .knowledge import TOPICS, match_topics
from .log import read_recent
from .runner import run_all_checks
from .vitals import analyze_vitals, read_vitals

TEMPLATE_DIR = Path(__file__).parent / "templates"


# ── SVG helpers (registered as Jinja2 globals) ──


def _donut_svg(score: int, grade: str, color: str, size: int = 130) -> str:
    r = size // 2 - 10
    cx = cy = size // 2
    circ = 2 * 3.14159 * r
    filled = score / 100 * circ
    gap = circ - filled
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#e2e8f0" stroke-width="10"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" stroke-width="10" '
        f'stroke-dasharray="{filled:.1f} {gap:.1f}" '
        f'stroke-linecap="round" transform="rotate(-90 {cx} {cy})"/>'
        f'<text x="{cx}" y="{cy - 8}" text-anchor="middle" '
        f'font-size="32" font-weight="800" fill="{color}" '
        f'font-family="SF Mono, monospace">{grade}</text>'
        f'<text x="{cx}" y="{cy + 14}" text-anchor="middle" '
        f'font-size="13" fill="#64748b" '
        f'font-family="SF Mono, monospace">{score}/100</text>'
        f"</svg>"
    )


def _bar_svg(value: int, max_val: int = 100, width: int = 200, height: int = 18) -> str:
    filled = int(value / max_val * width)
    color = "#22c55e" if value >= 80 else "#eab308" if value >= 50 else "#ef4444"
    return (
        f'<svg width="{width}" height="{height}">'
        f'<rect width="{width}" height="{height}" rx="3" fill="#e2e8f0"/>'
        f'<rect width="{filled}" height="{height}" rx="3" fill="{color}"/>'
        f"</svg>"
    )


def _sparkline_svg(values: list[float], width: int = 500, height: int = 60) -> str:
    if not values:
        return ""
    mn, mx = min(values), max(values)
    rng = mx - mn if mx != mn else 1
    if len(values) > 80:
        step = len(values) / 80
        values = [values[int(i * step)] for i in range(80)]
    points = []
    for i, v in enumerate(values):
        x = i / max(len(values) - 1, 1) * width
        y = height - ((v - mn) / rng * (height - 4)) - 2
        points.append(f"{x:.1f},{y:.1f}")
    polyline = " ".join(points)
    area = f"0,{height} " + polyline + f" {width},{height}"
    return (
        f'<svg width="{width}" height="{height}" style="display:block">'
        f'<polygon points="{area}" fill="rgba(14,116,144,0.12)"/>'
        f'<polyline points="{polyline}" fill="none" stroke="#0e7490" stroke-width="1.5"/>'
        f"</svg>"
    )


def _mini_sparkline(values: list[float], width: int = 80, height: int = 16) -> str:
    if not values or len(values) < 2:
        return '<span style="color:#94a3b8">—</span>'
    mn, mx = min(values), max(values)
    rng = mx - mn if mx != mn else 1
    points = []
    for i, v in enumerate(values):
        x = i / max(len(values) - 1, 1) * width
        y = height - ((v - mn) / rng * (height - 2)) - 1
        points.append(f"{x:.0f},{y:.0f}")
    return (
        f'<svg width="{width}" height="{height}" style="vertical-align:middle">'
        f'<polyline points="{" ".join(points)}" fill="none" stroke="#0e7490" stroke-width="1.5"/>'
        f"</svg>"
    )


def _cpu_bar(cpu_str: str, max_cpu: float) -> str:
    cpu = float(cpu_str)
    bar_w = int(cpu / max(max_cpu, 1) * 140)
    color = "#ef4444" if cpu > 50 else "#ca8a04" if cpu > 20 else "#0284c7"
    return (
        f'<div style="display:flex;align-items:center;gap:6px">'
        f'<div style="width:{bar_w}px;height:12px;background:{color};border-radius:2px"></div>'
        f'<span class="mono">{cpu_str}%</span></div>'
    )


def _mem_bar(mem_str: str, max_mem: float, ram_gb: int) -> str:
    mem_pct = float(mem_str)
    mem_gb = round(mem_pct / 100 * ram_gb, 1)
    bar_w = int(mem_pct / max(max_mem, 1) * 140)
    color = "#ef4444" if mem_pct > 10 else "#ca8a04" if mem_pct > 5 else "#0284c7"
    return (
        f'<div style="display:flex;align-items:center;gap:6px">'
        f'<div style="width:{bar_w}px;height:12px;background:{color};border-radius:2px"></div>'
        f'<span class="mono">{mem_gb} GB</span></div>'
    )


def _mem_gb(mem_str: str, ram_gb: int) -> str:
    return str(round(float(mem_str) / 100 * ram_gb, 1))


def _size_bar(size_mb: int, max_size: int) -> str:
    bar_w = int(size_mb / max(max_size, 1) * 140)
    size_str = f"{size_mb} MB" if size_mb < 1024 else f"{size_mb / 1024:.1f} GB"
    color = "#ef4444" if size_mb > 500 else "#ca8a04" if size_mb > 100 else "#0284c7"
    return (
        f'<div style="display:flex;align-items:center;gap:6px">'
        f'<div style="width:{bar_w}px;height:12px;background:{color};border-radius:2px"></div>'
        f'<span class="mono">{size_str}</span></div>'
    )


def _bar_html(value: float, max_val: float, threshold: float) -> str:
    bar_w = int(value / max(max_val, 1) * 140)
    color = "#ef4444" if threshold > 30 else "#ca8a04" if threshold > 10 else "#0284c7"
    return (
        f'<div style="display:flex;align-items:center;gap:6px">'
        f'<div style="width:{bar_w}px;height:12px;background:{color};border-radius:2px"></div>'
        f'<span class="mono">{value:.0f}%·s</span></div>'
    )


def _sev_badge(severity: str) -> str:
    colors = {
        "critical": ("#ef4444", "#fff"),
        "warning": ("#ca8a04", "#fff"),
        "info": ("#3b82f6", "#fff"),
        "ok": ("#22c55e", "#fff"),
    }
    bg, fg = colors.get(severity, ("#64748b", "#fff"))
    return (
        f'<span style="background:{bg};color:{fg};padding:1px 8px;border-radius:3px;'
        f'font-size:11px;font-weight:600;text-transform:uppercase">{severity}</span>'
    )


def _knowledge_card(topic_keys: list[str]) -> str:
    html = ""
    for key in topic_keys:
        topic = TOPICS.get(key)
        if not topic:
            continue
        title = key.replace("_", " ").title()
        html += (
            f'<details class="knowledge"><summary>{title} — what is this?</summary>'
            f'<div class="k-section"><b>What:</b> {topic["what"]}</div>'
            f'<div class="k-section"><b>Why it matters:</b> {topic["why"]}</div>'
            f'<div class="k-section"><b>How to fix:</b><br>{topic["fix"].replace(chr(10), "<br>")}</div>'
            f"</details>"
        )
    return html


# ── Process identification ──


def _process_action(name: str, cmdline: str = "") -> str:
    system = {
        "WindowServer": "System — reduce windows/displays",
        "kernel_task": "Thermal management — reduce workload",
        "mds_stores": "Spotlight indexing — wait or exclude folders",
        "mds": "Spotlight — transient",
        "fileproviderd": "Cloud sync — pause OneDrive/iCloud",
        "trustd": "Certificate validation — transient",
        "XprotectService": "Security scan — transient",
        "mediaanalysisd": "Photo analysis — transient",
        "bird": "iCloud sync — transient",
        "launchd": "System init — cannot be killed",
    }
    if name in system:
        return system[name]
    third_party = {
        "OneDrive": "Pause sync",
        "Dropbox": "Pause sync",
        "Docker Desktop": "Check resource limits",
        "prl_client_app": "Suspend VM",
    }
    for key, advice in third_party.items():
        if key.lower() in name.lower():
            return advice
    if cmdline:
        return _identify_from_cmdline(cmdline)
    return f'<span class="action-cmd">kill -15 $(pgrep -f "{name}")</span>'


def _identify_from_cmdline(cmdline: str) -> str:
    parts = cmdline.split()
    binary = parts[0].rsplit("/", 1)[-1] if parts else "?"
    if "python" in binary.lower():
        if "uvicorn" in cmdline or "gunicorn" in cmdline:
            for i, p in enumerate(parts):
                if "uvicorn" in p or "gunicorn" in p:
                    app = parts[i + 1].split(":")[0] if i + 1 < len(parts) else "?"
                    return f"Web server: <code>{app}</code>"
        if " -m " in cmdline:
            module = cmdline.split(" -m ")[-1].strip().split()[0]
            return f"Module: <code>{module}</code>"
        for p in parts[1:]:
            if p.startswith("-"):
                continue
            if "/bin/" in p and not p.rsplit("/", 1)[-1].startswith("python"):
                return f"<code>{p.rsplit('/', 1)[-1]}</code>"
            if p.endswith(".py"):
                path_parts = p.rsplit("/", 2)
                script = path_parts[-1].replace(".py", "")
                parent = path_parts[-2] if len(path_parts) >= 2 else ""
                return (
                    f"Script: <code>{parent}/{script}</code>"
                    if parent
                    else f"Script: <code>{script}</code>"
                )
            break
    if "node" in binary.lower():
        for p in parts[1:]:
            if p.endswith(".js") or p.endswith(".ts"):
                return f"<code>{p.rsplit('/', 1)[-1]}</code>"
    if "claude" in cmdline.lower():
        return "Claude Code session"
    if "run-daemon" in cmdline or "run-server" in cmdline:
        for p in parts:
            if "run-daemon" in p or "run-server" in p:
                service = p.split("/")[-3] if p.count("/") >= 3 else p.rsplit("/", 1)[-1]
                return f"Daemon: <code>{service}</code>"
    short = cmdline[:80] + ("..." if len(cmdline) > 80 else "")
    return f'<code style="font-size:11px;color:#475569">{short}</code>'


def _is_daemon(cmdline: str) -> bool:
    cl = cmdline.lower()
    app_signals = [
        "/Applications/",
        ".app/Contents/MacOS/",
        "Electron",
        "iTerm",
        "Chrome",
        "Safari",
        "Firefox",
        "Cursor",
        "Xcode",
    ]
    for sig in app_signals:
        if sig.lower() in cl:
            return False
    daemon_signals = [
        "launchd",
        "daemon",
        "run-server",
        "run-daemon",
        "uvicorn",
        "gunicorn",
        "celery",
        "worker",
        "/usr/sbin/",
        "/usr/libexec/",
        "com.apple.",
        "com.reeves.",
        "com.tosh.",
        "com.eidos",
        "-m ",
        "python3 -",
    ]
    for sig in daemon_signals:
        if sig in cl:
            return True
    if any(p in cl for p in ["/repos-", "/opt/homebrew/", "/.local/", "/.venv/"]):
        return True
    return False


def _get_live_process_tables() -> tuple[list[dict], list[dict]]:
    cpu_hogs, mem_hogs = [], []
    cmdlines: dict[str, str] = {}
    try:
        out = subprocess.run(["ps", "-eo", "pid,args"], capture_output=True, text=True, timeout=5)
        if out.returncode == 0:
            for line in out.stdout.strip().split("\n")[1:]:
                parts = line.strip().split(None, 1)
                if len(parts) == 2:
                    cmdlines[parts[0]] = parts[1]
    except (subprocess.TimeoutExpired, OSError):
        pass
    try:
        out = subprocess.run(
            ["ps", "-eo", "pid,pcpu,pmem,comm", "-r"], capture_output=True, text=True, timeout=5
        )
        if out.returncode == 0:
            for line in out.stdout.strip().split("\n")[1:15]:
                parts = line.split(None, 3)
                if len(parts) < 4:
                    continue
                pid, cpu, mem, comm = parts
                if float(cpu) < 5:
                    break
                cpu_hogs.append(
                    {
                        "pid": pid,
                        "cpu": cpu,
                        "mem": mem,
                        "name": comm.rsplit("/", 1)[-1],
                        "cmdline": cmdlines.get(pid, ""),
                    }
                )
        out = subprocess.run(
            ["ps", "-eo", "pid,pcpu,pmem,comm", "-m"], capture_output=True, text=True, timeout=5
        )
        if out.returncode == 0:
            for line in out.stdout.strip().split("\n")[1:15]:
                parts = line.split(None, 3)
                if len(parts) < 4:
                    continue
                pid, cpu, mem, comm = parts
                if float(mem) < 1.0:
                    break
                mem_hogs.append(
                    {
                        "pid": pid,
                        "cpu": cpu,
                        "mem": mem,
                        "name": comm.rsplit("/", 1)[-1],
                        "cmdline": cmdlines.get(pid, ""),
                    }
                )
    except (subprocess.TimeoutExpired, OSError):
        pass
    return cpu_hogs, mem_hogs


_TRADEOFF_MAP = {
    "swap": {
        "gain": "Faster app switching, no more random freezes, reduced SSD wear",
        "lose": "Need to close some apps or reboot — temporary disruption",
    },
    "disk": {
        "gain": "Faster writes, swap can grow when needed, macOS updates work again",
        "lose": "Time spent cleaning up files",
    },
    "orphaned": {
        "gain": "Fewer wasted process spawns, cleaner launchd, less log noise",
        "lose": "Nothing — these agents serve no purpose, their app is already gone",
    },
    "outdated": {
        "gain": "Security patches, bug fixes, compatibility with newer tools",
        "lose": "Possible breaking changes — review changelogs before upgrading all at once",
    },
    "crash-loop": {
        "gain": "CPU freed from restart cycles, fewer kernel panic triggers",
        "lose": "The service stops running — check if anything depends on it first",
    },
}


def _get_tradeoff_fn(finding: dict) -> dict | None:
    summary = finding.get("summary", "").lower()
    check = finding.get("check", "").lower()
    if "swap" in summary:
        return _TRADEOFF_MAP["swap"]
    if "disk" in check and ("full" in summary or "free" in summary):
        return _TRADEOFF_MAP["disk"]
    if "orphaned" in summary:
        return _TRADEOFF_MAP["orphaned"]
    if "outdated" in summary and "homebrew" in check:
        return _TRADEOFF_MAP["outdated"]
    if "crash-looping" in summary or "crash loop" in summary:
        return _TRADEOFF_MAP["crash-loop"]
    return None


# ── Uptime ──


def _get_uptime() -> str:
    try:
        out = subprocess.run(
            ["sysctl", "-n", "kern.boottime"], capture_output=True, text=True, timeout=5
        )
        boot_sec = int(out.stdout.split("sec = ")[1].split(",")[0])
        uptime_sec = int(datetime.now().timestamp()) - boot_sec
        days = uptime_sec // 86400
        hours = (uptime_sec % 86400) // 3600
        return f"{days}d {hours}h" if days > 0 else f"{hours}h {(uptime_sec % 3600) // 60}m"
    except Exception:
        return "?"


# ── BLUF ──


def _generate_bluf(criticals, warnings, infos, spikes) -> str:
    if not criticals and not warnings:
        return "Your Mac is healthy. No critical or warning-level issues detected."
    parts = []
    if criticals:
        by_check: dict[str, int] = {}
        for c in criticals:
            by_check[c["check"]] = by_check.get(c["check"], 0) + 1
        top_check = max(by_check, key=by_check.get)  # type: ignore[arg-type]
        top_count = by_check[top_check]
        bluf_map = {
            "Kernel Panics": f"Your Mac has kernel-panicked {top_count} times recently — processes are starving the CPU watchdog",
            "Crash Loops": f"{top_count} process(es) crash-looping — burning CPU on restart cycles",
            "CPU Load": "Sustained high CPU load is causing system-wide slowdowns",
            "Thermal": "Your Mac is thermally throttled — running at reduced speed to prevent heat damage",
            "Shutdown Causes": f"{top_count} abnormal shutdown(s) detected",
            "Memory Pressure": "Your Mac is under heavy memory pressure, swapping to SSD",
            "Disk Health": "Disk space critically low — macOS needs free space for swap, caches, and updates",
        }
        parts.append(bluf_map.get(top_check, f"{len(criticals)} critical issue(s) in {top_check}"))
    if warnings:
        warn_checks = set(w["check"] for w in warnings)
        if "Memory Pressure" in warn_checks and any("Swap" in w["summary"] for w in warnings):
            parts.append("high swap usage is forcing your Mac to run on SSD instead of RAM")
        elif len(warn_checks) == 1:
            parts.append(f"{len(warnings)} warning(s) in {warn_checks.pop()}")
        else:
            parts.append(f"{len(warnings)} warning(s) across {len(warn_checks)} areas")
    if spikes and any(s.get("ongoing") for s in spikes):
        parts.append("a load spike is happening right now")
    return ". ".join(parts) + "." if parts else "Review the findings below."


# ── Score matrix ──


def _compute_matrix(report) -> dict:
    dim_checks = {
        "stability": ["Crash Loops", "Kernel Panics", "Shutdown Causes"],
        "cpu": ["CPU Load"],
        "thermal": ["Thermal"],
        "memory": ["Memory Pressure"],
        "storage": ["Disk Health"],
        "services": ["Launch Agents"],
        "security": ["Security"],
        "infra": ["Dynamic Library Health", "Homebrew"],
        "network": ["Network"],
    }
    weights = {
        "stability": 3,
        "cpu": 3,
        "memory": 2,
        "thermal": 2,
        "storage": 2,
        "services": 2,
        "security": 1,
        "infra": 1,
        "network": 1,
    }
    check_scores = {}
    for r in report.results:
        score = 100
        for f in r.findings:
            s = f.severity.value
            if s == "critical":
                score = min(score, 0)
            elif s == "warning":
                score = min(score, 50)
            elif s == "info":
                score = min(score, 80)
        check_scores[r.name] = score
    matrix = {}
    for dim, checks in dim_checks.items():
        scores = [check_scores.get(c, 100) for c in checks]
        matrix[dim] = min(scores) if scores else 100
    weighted_sum = sum(matrix.get(d, 100) * w for d, w in weights.items())
    overall = round(weighted_sum / sum(weights.values()))
    grade = (
        "A"
        if overall >= 90
        else "B"
        if overall >= 75
        else "C"
        if overall >= 50
        else "D"
        if overall >= 25
        else "F"
    )
    return {**matrix, "_overall": overall, "_grade": grade}


# ── Action plan ──


def _build_action_plan(
    criticals, warnings, spikes, offenders, stale_apps, redundant_apps, matrix=None
) -> dict:
    # Score gain estimation: fixing a dimension from 0→100 or 50→100
    # weighted by dimension weight, divided by total weight (17)
    def _est_gain(dim: str, current: int, target: int = 100) -> int:
        weights = {
            "stability": 3,
            "cpu": 3,
            "memory": 2,
            "thermal": 2,
            "storage": 2,
            "services": 2,
            "security": 1,
            "infra": 1,
            "network": 1,
        }
        w = weights.get(dim, 1)
        return round((target - current) * w / 17)

    m = matrix or {}

    immediate, longterm = [], []
    for item in criticals:
        if "crash-looping" in item["summary"].lower() or "crash loop" in item["summary"].lower():
            immediate.append(
                {
                    "action": f"Stop crash loop: {item['summary'][:50]}",
                    "impact": "Frees CPU from restart cycles",
                    "effort": "1 min",
                    "cmd": item.get("fix", ""),
                    "score_gain": _est_gain("services", m.get("services", 0)),
                }
            )
    if spikes and any(s.get("ongoing") for s in spikes):
        s = next(s for s in spikes if s.get("ongoing"))
        procs = ", ".join(p[1] for p in s.get("top_processes", [])[:3])
        immediate.append(
            {
                "action": f"Active load spike (peak {s['peak_load']:.0f}x)",
                "impact": f"Culprits: {procs}",
                "effort": "5 min",
                "cmd": "",
                "score_gain": _est_gain("cpu", m.get("cpu", 0)),
            }
        )
    sustained = [o for o in offenders if o.get("sustained")]
    for o in sustained[:2]:
        immediate.append(
            {
                "action": f"Investigate {o['name']} — {o['avg_cpu']}% avg CPU",
                "impact": f"Sustained strain: {o['total_cpu']:.0f} cumulative CPU-seconds",
                "effort": "10 min",
                "cmd": "",
                "score_gain": 0,
            }
        )
    panics = [c for c in criticals if c["check"] == "Kernel Panics"]
    if len(panics) >= 5:
        immediate.append(
            {
                "action": f"Resolve kernel panic pattern ({len(panics)} panics)",
                "impact": "Mac will keep crashing until fixed",
                "effort": "30 min",
                "cmd": "aad checkup -c kernel_panics -c cpu_load --json",
                "score_gain": _est_gain("stability", m.get("stability", 0)),
            }
        )
    if any("swap" in w["summary"].lower() for w in warnings):
        immediate.append(
            {
                "action": "Reduce memory pressure",
                "impact": "Mac is using SSD as RAM, slowing everything",
                "effort": "5 min",
                "cmd": "See Memory Hogs table",
                "score_gain": _est_gain("memory", m.get("memory", 0), 100),
            }
        )
    orphans = [w for w in warnings if "orphaned" in w["summary"].lower()]
    if orphans:
        longterm.append(
            {
                "action": "Remove orphaned launch agents",
                "impact": "Eliminates wasted process spawns",
                "effort": "5 min",
                "cmd": orphans[0].get("fix", ""),
                "score_gain": 2,
            }
        )
    if redundant_apps:
        names = [r["unused"]["name"] for r in redundant_apps[:3]]
        longterm.append(
            {
                "action": f"Uninstall {len(redundant_apps)} replaced app(s): {', '.join(names)}",
                "impact": "Reclaim disk, reduce background processes",
                "effort": "10 min",
                "cmd": "",
                "score_gain": _est_gain("storage", m.get("storage", 50), 100),
            }
        )
    elif stale_apps:
        longterm.append(
            {
                "action": f"Review {len(stale_apps)} unused apps",
                "impact": "Reclaim disk space",
                "effort": "15 min",
                "cmd": "",
                "score_gain": _est_gain("storage", m.get("storage", 50), 100),
            }
        )
    if any(
        "disk" in w["check"].lower()
        and ("full" in w["summary"].lower() or "free" in w["summary"].lower())
        for w in warnings
    ):
        longterm.append(
            {
                "action": "Free disk space",
                "impact": "Prevents swap failures, enables updates",
                "effort": "20 min",
                "cmd": "sudo tmutil thinlocalsnapshots / 9999999999 1",
                "score_gain": _est_gain("storage", m.get("storage", 0)),
            }
        )
    brew = [w for w in warnings if w["check"] == "Homebrew"]
    if len(brew) >= 3:
        longterm.append(
            {
                "action": "Homebrew maintenance",
                "impact": "Security patches, reclaim cache space",
                "effort": "15 min",
                "cmd": "brew upgrade && brew cleanup",
                "score_gain": _est_gain("infra", m.get("infra", 0)),
            }
        )
    from .launchd import _plist_path

    if not _plist_path().exists():
        longterm.append(
            {
                "action": "Install vitals monitor",
                "impact": "Better sustained pressure data in future reports",
                "effort": "1 min",
                "cmd": "aad install",
                "score_gain": 0,
            }
        )
    return {"immediate": immediate[:5], "longterm": longterm[:5]}


# ── Scatterplot ──


def _cleanup_scatterplot(stale_apps: list[dict], width: int = 780, height: int = 320) -> str:
    if not stale_apps:
        return ""
    pad_l, pad_r, pad_t, pad_b = 60, 20, 20, 40
    plot_w, plot_h = width - pad_l - pad_r, height - pad_t - pad_b
    max_days = min(max(a.get("days_ago", 1) for a in stale_apps), 365)
    max_size = max(max(a.get("size_mb", 1) for a in stale_apps), 100)
    mid_x, mid_y = pad_l + plot_w * 0.5, pad_t + plot_h * 0.5
    svg = f'<svg width="{width}" height="{height}" style="display:block;margin:8px 0">\n'
    svg += f'<rect x="{mid_x}" y="{pad_t}" width="{plot_w * 0.5}" height="{plot_h * 0.5}" fill="rgba(239,68,68,0.05)" rx="4"/>\n'
    svg += f'<text x="{mid_x + plot_w * 0.25}" y="{pad_t + 16}" text-anchor="middle" font-size="11" fill="#dc2626" font-weight="600">Suggest Removal</text>\n'
    svg += f'<text x="{pad_l + plot_w * 0.25}" y="{pad_t + 16}" text-anchor="middle" font-size="11" fill="#64748b">Keep (watch size)</text>\n'
    svg += f'<text x="{mid_x + plot_w * 0.25}" y="{pad_t + plot_h - 4}" text-anchor="middle" font-size="11" fill="#64748b">Low priority</text>\n'
    svg += f'<text x="{pad_l + plot_w * 0.25}" y="{pad_t + plot_h - 4}" text-anchor="middle" font-size="11" fill="#22c55e">Fine</text>\n'
    svg += f'<line x1="{mid_x}" y1="{pad_t}" x2="{mid_x}" y2="{pad_t + plot_h}" stroke="#e2e8f0" stroke-dasharray="4"/>\n'
    svg += f'<line x1="{pad_l}" y1="{mid_y}" x2="{pad_l + plot_w}" y2="{mid_y}" stroke="#e2e8f0" stroke-dasharray="4"/>\n'
    svg += f'<line x1="{pad_l}" y1="{pad_t + plot_h}" x2="{pad_l + plot_w}" y2="{pad_t + plot_h}" stroke="#94a3b8"/>\n'
    svg += (
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t + plot_h}" stroke="#94a3b8"/>\n'
    )
    svg += f'<text x="{pad_l + plot_w // 2}" y="{height - 4}" text-anchor="middle" font-size="12" fill="#64748b">Days since last use →</text>\n'
    svg += f'<text x="14" y="{pad_t + plot_h // 2}" text-anchor="middle" font-size="12" fill="#64748b" transform="rotate(-90 14 {pad_t + plot_h // 2})">Size (MB) →</text>\n'
    for app in stale_apps:
        days = min(app.get("days_ago", 30), max_days)
        size = min(app.get("size_mb", 0), max_size)
        x = pad_l + (days - 30) / max(max_days - 30, 1) * plot_w
        y = pad_t + plot_h - (size / max_size * plot_h)
        in_remove = days > max_days * 0.5 and size > max_size * 0.3
        color = "#ef4444" if in_remove else "#0284c7"
        r = max(4, min(12, size / max_size * 15 + 3))
        svg += f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r:.0f}" fill="{color}" opacity="0.7"><title>{app["name"]}</title></circle>\n'
        if size > max_size * 0.15 or in_remove:
            svg += f'<text x="{x + r + 3:.0f}" y="{y + 4:.0f}" font-size="10" fill="#475569">{app["name"][:20]}</text>\n'
    svg += "</svg>"
    return svg


# ── Main entry points ──


def generate_html_report(vitals_minutes: int = 60) -> str:
    """Collect all data and render via Jinja2 templates."""
    report = run_all_checks(parallel=True)
    vitals_data = analyze_vitals(minutes=vitals_minutes)
    history = read_recent(10)
    samples = read_vitals(minutes=vitals_minutes)
    cores = os.cpu_count() or 8
    info = report.mac_info
    uptime = _get_uptime()
    ram_gb = info.get("memory_gb", 0)

    # Findings
    criticals, warnings, infos = [], [], []
    for r in report.results:
        for f in r.findings:
            entry = {
                "check": r.name,
                "summary": f.summary,
                "fix": f.fix,
                "details": f.details,
                "severity": f.severity.value,
            }
            if f.severity.value == "critical":
                criticals.append(entry)
            elif f.severity.value == "warning":
                warnings.append(entry)
            elif f.severity.value == "info":
                infos.append(entry)

    # Matrix
    matrix = _compute_matrix(report)
    overall = matrix.pop("_overall", 0)
    grade = matrix.pop("_grade", "?")
    grade_color = {
        "A": "#22c55e",
        "B": "#22c55e",
        "C": "#ca8a04",
        "D": "#ef4444",
        "F": "#ef4444",
    }.get(grade, "#94a3b8")

    # Vitals
    spikes = vitals_data.get("load", {}).get("spikes", [])
    offenders = vitals_data.get("worst_offenders", [])
    sustained = [o for o in offenders if o.get("sustained")]
    transient = [o for o in offenders if not o.get("sustained")]

    # Load
    load_values = [s["load"][0] for s in samples if "load" in s] if samples else []

    # System info — swap from vitals or direct sysctl
    swap_mb = vitals_data.get("swap", {}).get("current_mb") or 0
    if not swap_mb:
        try:
            out = subprocess.run(
                ["sysctl", "vm.swapusage"], capture_output=True, text=True, timeout=5
            )
            if out.returncode == 0 and "used" in out.stdout:
                swap_mb = float(out.stdout.split("used = ")[1].split(" ")[0].rstrip("M"))
        except Exception:
            pass
    swap_gb = round(swap_mb / 1024, 1)
    swap_pct = int(swap_gb / ram_gb * 100) if ram_gb else 0
    swap_color = "#ef4444" if swap_pct > 50 else "#ca8a04" if swap_pct > 25 else "#22c55e"
    current_load = (
        samples[-1]["load"][0] if samples and "load" in samples[-1] else os.getloadavg()[0]
    )
    load_pct = int(current_load / cores * 100) if cores else 0
    load_color = "#ef4444" if load_pct > 200 else "#ca8a04" if load_pct > 100 else "#22c55e"

    # Disk — use diskutil for accurate APFS numbers
    disk_total_gb = disk_used_gb = disk_free_gb = disk_pct = 0
    try:
        out = subprocess.run(["diskutil", "info", "/"], capture_output=True, text=True, timeout=10)
        if out.returncode == 0:
            for line in out.stdout.split("\n"):
                if "Container Total Space" in line or "Volume Total Space" in line:
                    # "Container Total Space:  926.4 GB (994662584320 Bytes)"
                    num = line.split(":")[1].strip().split()[0]
                    disk_total_gb = int(float(num))
                elif "Volume Available Space" in line or "Container Free Space" in line:
                    num = line.split(":")[1].strip().split()[0]
                    disk_free_gb = int(float(num))
            if disk_total_gb and disk_free_gb:
                disk_used_gb = disk_total_gb - disk_free_gb
                disk_pct = int(disk_used_gb / disk_total_gb * 100)
    except Exception:
        # Fallback to df with corrected math
        try:
            out = subprocess.run(["df", "-g", "/"], capture_output=True, text=True, timeout=5)
            if out.returncode == 0:
                parts = out.stdout.strip().split("\n")[1].split()
                disk_total_gb = int(parts[1])
                disk_avail_gb = int(parts[3])
                disk_used_gb = disk_total_gb - disk_avail_gb
                disk_pct = int(disk_used_gb / disk_total_gb * 100) if disk_total_gb else 0
        except Exception:
            pass
    disk_color = "#ef4444" if disk_pct > 90 else "#ca8a04" if disk_pct > 75 else "#22c55e"

    # Process tables
    cpu_hogs, mem_hogs = _get_live_process_tables()
    daemon_hogs = [p for p in cpu_hogs if _is_daemon(p.get("cmdline", ""))]
    app_cpu_hogs = [p for p in cpu_hogs if not _is_daemon(p.get("cmdline", ""))]

    # Criticals grouped
    criticals_by_check = {}
    for c in criticals:
        criticals_by_check.setdefault(c["check"], []).append(c)
    criticals_by_check_sorted = sorted(criticals_by_check.items(), key=lambda x: -len(x[1]))

    # Matrix dimensions
    dim_check_map = {
        "stability": ["Crash Loops", "Kernel Panics", "Shutdown Causes"],
        "cpu": ["CPU Load"],
        "thermal": ["Thermal"],
        "memory": ["Memory Pressure"],
        "storage": ["Disk Health"],
        "services": ["Launch Agents"],
        "security": ["Security"],
        "infra": ["Dynamic Library Health", "Homebrew"],
        "network": ["Network"],
    }
    all_findings = criticals + warnings
    dimensions = []
    for dim, label in [
        ("stability", "Stability"),
        ("cpu", "CPU"),
        ("thermal", "Thermal"),
        ("memory", "Memory"),
        ("storage", "Storage"),
        ("services", "Services"),
        ("security", "Security"),
        ("infra", "Infra"),
        ("network", "Network"),
    ]:
        val = matrix.get(dim, 100)
        issue = ""
        for item in all_findings:
            if item["check"] in dim_check_map.get(dim, []):
                issue = item["summary"]
                break
        dimensions.append(
            {"dim": dim, "label": label, "value": val, "bar_svg": _bar_svg(val), "issue": issue}
        )

    # Cleanup
    stale_apps = _find_stale_apps()
    remove_candidates = [a for a in stale_apps if a.get("days_ago", 0) > 90]

    # Similar apps (ensemble ranking)
    from .ensemble_similarity import ensemble_score as _ensemble_score
    from .app_similarity import get_app_metadata as _get_meta

    _sim_apps = {}
    for app_path in _glob.glob("/Applications/*.app"):
        name = os.path.basename(app_path).replace(".app", "")
        if name in _SAFE_APPS:
            continue
        try:
            _sim_apps[name] = _get_meta(app_path)
        except Exception:
            pass
    similar_pairs = []
    _sim_names = list(_sim_apps.keys())
    for i, name_a in enumerate(_sim_names):
        for name_b in _sim_names[i + 1 :]:
            score, reasons = _ensemble_score(_sim_apps[name_a], _sim_apps[name_b])
            if score > 0.3 and reasons:
                similar_pairs.append(
                    {
                        "app_a": name_a,
                        "app_b": name_b,
                        "score": score,
                        "reasons": ". ".join(reasons),
                    }
                )
    similar_pairs.sort(key=lambda x: x["score"], reverse=True)
    similar_pairs = similar_pairs[:10]

    # Legacy: keep redundant for action plan compatibility
    all_apps_for_sim = []
    for app_path in _glob.glob("/Applications/*.app"):
        name = os.path.basename(app_path).replace(".app", "")
        if name in _SAFE_APPS:
            continue
        lu = _get_last_used(app_path)
        days_ago = 999
        if lu:
            try:
                d = datetime.fromisoformat(lu.replace(" +0000", "+00:00"))
                days_ago = (datetime.now(timezone.utc) - d).days
            except ValueError:
                pass
        all_apps_for_sim.append({"name": name, "path": app_path, "days_ago": days_ago})
    redundant = find_redundant_apps(all_apps_for_sim)

    # Action plan
    action_plan = _build_action_plan(
        criticals, warnings, spikes, offenders, stale_apps, redundant, matrix
    )

    # Trend
    trend = None
    if len(history) >= 3:
        recent_c = sum(e.get("counts", {}).get("critical", 0) for e in history[-3:]) / 3
        older_c = sum(e.get("counts", {}).get("critical", 0) for e in history[:3]) / 3
        trend = (
            "improving" if recent_c < older_c else "degrading" if recent_c > older_c else "stable"
        )

    # Render
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=False)
    env.globals.update(
        {
            "sev_badge": _sev_badge,
            "knowledge_card": _knowledge_card,
            "match_topics": match_topics,
            "get_tradeoff": _get_tradeoff_fn,
            "process_action": _process_action,
            "mini_sparkline": _mini_sparkline,
            "cpu_bar": _cpu_bar,
            "mem_bar": _mem_bar,
            "mem_gb": _mem_gb,
            "bar_html": _bar_html,
            "size_bar": _size_bar,
        }
    )

    template = env.get_template("report.html")
    return template.render(
        grade=grade,
        overall=overall,
        grade_color=grade_color,
        now_str=datetime.now().strftime("%Y-%m-%d %H:%M"),
        duration_ms=report.duration_ms,
        mac=info,
        cores=cores,
        ram_gb=ram_gb,
        donut_svg=_donut_svg(overall, grade, grade_color),
        bluf_text=_generate_bluf(criticals, warnings, infos, spikes),
        criticals=criticals,
        warnings=warnings,
        infos=infos,
        criticals_by_check=criticals_by_check_sorted,
        dimensions=dimensions,
        # Sysinfo
        current_load=current_load,
        load_pct=load_pct,
        load_color=load_color,
        swap_gb=swap_gb,
        swap_pct=swap_pct,
        swap_color=swap_color,
        disk_used_gb=disk_used_gb,
        disk_total_gb=disk_total_gb,
        disk_pct=disk_pct,
        disk_color=disk_color,
        uptime=uptime,
        # Load
        load_values=load_values,
        load_peak=max(load_values) if load_values else 0,
        load_avg=sum(load_values) / len(load_values) if load_values else 0,
        sparkline_svg=_sparkline_svg(load_values, width=780, height=70) if load_values else "",
        spikes=spikes,
        # Pressure
        sustained=sustained,
        transient=transient,
        max_sustained_cpu=max(o["total_cpu"] for o in sustained) if sustained else 1,
        max_transient_peak=max(o["peak_cpu"] for o in transient[:5]) if transient else 1,
        # Hogs
        daemon_hogs=daemon_hogs,
        app_cpu_hogs=app_cpu_hogs,
        mem_hogs=mem_hogs,
        max_daemon_cpu=max(float(p["cpu"]) for p in daemon_hogs) if daemon_hogs else 1,
        max_app_cpu=max(float(p["cpu"]) for p in app_cpu_hogs) if app_cpu_hogs else 1,
        max_mem_pct=max(float(p["mem"]) for p in mem_hogs) if mem_hogs else 1,
        # Cleanup
        stale_apps=stale_apps,
        remove_candidates=remove_candidates,
        scatterplot_svg=_cleanup_scatterplot(stale_apps),
        max_remove_size=max(a.get("size_mb", 1) for a in remove_candidates)
        if remove_candidates
        else 1,
        # Similarity
        similar_pairs=similar_pairs,
        redundant=redundant,
        # Actions
        immediate=action_plan["immediate"],
        longterm=action_plan["longterm"],
        # Trend
        trend=trend,
        # JSON download
        report_json=_build_report_json(
            grade,
            overall,
            matrix,
            criticals,
            warnings,
            infos,
            action_plan,
            trend,
            info,
            cores,
            ram_gb,
            uptime,
        ),
    )


def _build_report_json(
    grade,
    overall,
    matrix,
    criticals,
    warnings,
    infos,
    action_plan,
    trend,
    mac_info,
    cores,
    ram_gb,
    uptime,
) -> str:
    """Build JSON blob for the download button."""
    import json

    data = {
        "grade": grade,
        "score": overall,
        "matrix": matrix,
        "mac": mac_info,
        "cores": cores,
        "ram_gb": ram_gb,
        "uptime": uptime,
        "criticals": criticals,
        "warnings": warnings,
        "infos": infos,
        "actions": action_plan,
        "trend": trend,
        "generated": datetime.now().isoformat(timespec="seconds"),
    }
    return json.dumps(data)


def open_report(vitals_minutes: int = 60) -> Path:
    html = generate_html_report(vitals_minutes=vitals_minutes)
    report_dir = Path.home() / ".config" / "eidos" / "aad-logs" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    # Timestamped copy for history
    ts = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    report_path = report_dir / f"report-{ts}.html"
    report_path.write_text(html)
    # Also write latest for quick access
    latest = report_dir / "report-latest.html"
    latest.write_text(html)
    webbrowser.open(f"file://{report_path}")
    return report_path
