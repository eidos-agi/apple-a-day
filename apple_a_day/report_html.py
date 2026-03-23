"""Render apple-a-day health report as a self-contained HTML file.

Design principles:
  - BLUF first, details second
  - Every finding explained in plain english (via knowledge.py)
  - Trade-off framing: what you gain vs what you lose
  - Sans-serif for prose, monospace for data
"""

import os
import subprocess
import webbrowser
from datetime import datetime
from pathlib import Path

from .knowledge import TOPICS, match_topics
from .log import read_recent
from .runner import run_all_checks
from .vitals import analyze_vitals, read_vitals


# ── SVG helpers ──

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
        f'</svg>'
    )


def _bar_svg(value: int, max_val: int = 100, width: int = 200, height: int = 18) -> str:
    filled = int(value / max_val * width)
    color = "#22c55e" if value >= 80 else "#eab308" if value >= 50 else "#ef4444"
    return (f'<svg width="{width}" height="{height}">'
            f'<rect width="{width}" height="{height}" rx="3" fill="#e2e8f0"/>'
            f'<rect width="{filled}" height="{height}" rx="3" fill="{color}"/>'
            f'</svg>')


def _sparkline_svg(values: list[float], width: int = 500, height: int = 60) -> str:
    if not values:
        return ""
    mn, mx = min(values), max(values)
    rng = mx - mn if mx != mn else 1
    max_points = 80
    if len(values) > max_points:
        step = len(values) / max_points
        values = [values[int(i * step)] for i in range(max_points)]
    points = []
    for i, v in enumerate(values):
        x = i / max(len(values) - 1, 1) * width
        y = height - ((v - mn) / rng * (height - 4)) - 2
        points.append(f"{x:.1f},{y:.1f}")
    polyline = " ".join(points)
    area = f"0,{height} " + polyline + f" {width},{height}"
    return (f'<svg width="{width}" height="{height}" style="display:block">'
            f'<polygon points="{area}" fill="rgba(14,116,144,0.12)"/>'
            f'<polyline points="{polyline}" fill="none" stroke="#0e7490" stroke-width="1.5"/>'
            f'</svg>')


def _offender_bar(appearances: int, max_app: int, peak_cpu: float) -> str:
    w = int(appearances / max(max_app, 1) * 150)
    color = "#ef4444" if peak_cpu > 80 else "#ca8a04" if peak_cpu > 30 else "#0284c7"
    return (f'<div style="display:inline-block;width:{w}px;height:14px;'
            f'background:{color};border-radius:2px;vertical-align:middle"></div>'
            f' <span style="color:#64748b;font-size:12px">{appearances}x · peak {peak_cpu}%</span>')


def _sev_badge(severity: str) -> str:
    colors = {
        "critical": ("#ef4444", "#fff"),
        "warning": ("#ca8a04", "#fff"),
        "info": ("#3b82f6", "#fff"),
        "ok": ("#22c55e", "#fff"),
    }
    bg, fg = colors.get(severity, ("#64748b", "#fff"))
    return (f'<span style="background:{bg};color:{fg};'
            f'padding:1px 8px;border-radius:3px;font-size:11px;font-weight:600;'
            f'text-transform:uppercase">{severity}</span>')


def _knowledge_card(topic_keys: list[str]) -> str:
    """Render expandable knowledge cards for matched topics."""
    if not topic_keys:
        return ""
    html = ""
    seen = set()
    for key in topic_keys:
        if key in seen:
            continue
        seen.add(key)
        topic = TOPICS.get(key)
        if not topic:
            continue
        title = key.replace("_", " ").title()
        html += (
            f'<details class="knowledge">'
            f'<summary>{title} — what is this?</summary>'
            f'<div class="k-section"><b>What:</b> {_esc(topic["what"])}</div>'
            f'<div class="k-section"><b>Why it matters:</b> {_esc(topic["why"])}</div>'
            f'<div class="k-section"><b>How to fix:</b><br>{_esc(topic["fix"]).replace(chr(10), "<br>")}</div>'
            f'</details>'
        )
    return html


def _cleanup_scatterplot(stale_apps: list[dict], width: int = 780, height: int = 320) -> str:
    """SVG scatterplot: X = days since last use, Y = app size (impact).

    Quadrants:
      Top-right: big + unused → REMOVE
      Top-left: big + used recently → KEEP (but watch)
      Bottom-right: small + unused → low priority
      Bottom-left: small + used → fine
    """
    if not stale_apps:
        return ""

    pad_l, pad_r, pad_t, pad_b = 60, 20, 20, 40
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b

    max_days = max(a.get("days_ago", 1) for a in stale_apps)
    max_days = min(max_days, 365)  # cap at 1 year
    max_size = max(a.get("size_mb", 1) for a in stale_apps)
    if max_size < 100:
        max_size = 100

    svg = f'<svg width="{width}" height="{height}" style="display:block;margin:8px 0">\n'

    # Background quadrants
    mid_x = pad_l + plot_w * 0.5
    mid_y = pad_t + plot_h * 0.5
    # Top-right: suggest removal (red tint)
    svg += f'<rect x="{mid_x}" y="{pad_t}" width="{plot_w * 0.5}" height="{plot_h * 0.5}" fill="rgba(239,68,68,0.05)" rx="4"/>\n'
    # Quadrant labels
    svg += f'<text x="{mid_x + plot_w * 0.25}" y="{pad_t + 16}" text-anchor="middle" font-size="11" fill="#dc2626" font-weight="600">Suggest Removal</text>\n'
    svg += f'<text x="{pad_l + plot_w * 0.25}" y="{pad_t + 16}" text-anchor="middle" font-size="11" fill="#64748b">Keep (watch size)</text>\n'
    svg += f'<text x="{mid_x + plot_w * 0.25}" y="{pad_t + plot_h - 4}" text-anchor="middle" font-size="11" fill="#64748b">Low priority</text>\n'
    svg += f'<text x="{pad_l + plot_w * 0.25}" y="{pad_t + plot_h - 4}" text-anchor="middle" font-size="11" fill="#22c55e">Fine</text>\n'

    # Grid lines
    svg += f'<line x1="{mid_x}" y1="{pad_t}" x2="{mid_x}" y2="{pad_t + plot_h}" stroke="#e2e8f0" stroke-dasharray="4"/>\n'
    svg += f'<line x1="{pad_l}" y1="{mid_y}" x2="{pad_l + plot_w}" y2="{mid_y}" stroke="#e2e8f0" stroke-dasharray="4"/>\n'

    # Axes
    svg += f'<line x1="{pad_l}" y1="{pad_t + plot_h}" x2="{pad_l + plot_w}" y2="{pad_t + plot_h}" stroke="#94a3b8"/>\n'
    svg += f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t + plot_h}" stroke="#94a3b8"/>\n'

    # Axis labels
    svg += f'<text x="{pad_l + plot_w // 2}" y="{height - 4}" text-anchor="middle" font-size="12" fill="#64748b">Days since last use →</text>\n'
    svg += f'<text x="14" y="{pad_t + plot_h // 2}" text-anchor="middle" font-size="12" fill="#64748b" transform="rotate(-90 14 {pad_t + plot_h // 2})">Size (MB) →</text>\n'

    # Tick labels
    svg += f'<text x="{pad_l}" y="{height - 22}" text-anchor="middle" font-size="10" fill="#94a3b8">30d</text>\n'
    svg += f'<text x="{pad_l + plot_w}" y="{height - 22}" text-anchor="middle" font-size="10" fill="#94a3b8">{max_days}d</text>\n'
    svg += f'<text x="{pad_l - 6}" y="{pad_t + plot_h + 4}" text-anchor="end" font-size="10" fill="#94a3b8">0</text>\n'
    svg += f'<text x="{pad_l - 6}" y="{pad_t + 4}" text-anchor="end" font-size="10" fill="#94a3b8">{max_size}MB</text>\n'

    # Data points
    for app in stale_apps:
        days = min(app.get("days_ago", 30), max_days)
        size = min(app.get("size_mb", 0), max_size)
        x = pad_l + (days - 30) / max(max_days - 30, 1) * plot_w
        y = pad_t + plot_h - (size / max_size * plot_h)

        # Color by quadrant position
        in_remove_quadrant = days > max_days * 0.5 and size > max_size * 0.3
        color = "#ef4444" if in_remove_quadrant else "#0284c7"
        r = max(4, min(12, size / max_size * 15 + 3))

        name = _esc(app["name"])
        size_label = f"{size}MB" if size < 1024 else f"{size / 1024:.1f}GB"
        svg += (f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r:.0f}" fill="{color}" opacity="0.7">'
                f'<title>{name} — {size_label}, {app.get("last_used", "?")}</title></circle>\n')

        # Label large or notable apps
        if size > max_size * 0.15 or in_remove_quadrant:
            svg += f'<text x="{x + r + 3:.0f}" y="{y + 4:.0f}" font-size="10" fill="#475569">{name[:20]}</text>\n'

    svg += '</svg>'
    return svg


def _get_live_process_tables() -> tuple[list[dict], list[dict]]:
    """Get current top CPU and memory consumers with full command lines."""
    cpu_hogs = []
    mem_hogs = []

    # Get full command lines for all PIDs in one shot
    cmdlines: dict[str, str] = {}
    try:
        out = subprocess.run(["ps", "-eo", "pid,args"],
                             capture_output=True, text=True, timeout=5)
        if out.returncode == 0:
            for line in out.stdout.strip().split("\n")[1:]:
                parts = line.strip().split(None, 1)
                if len(parts) == 2:
                    cmdlines[parts[0]] = parts[1]
    except (subprocess.TimeoutExpired, OSError):
        pass

    try:
        # CPU sorted
        out = subprocess.run(["ps", "-eo", "pid,pcpu,pmem,comm", "-r"],
                             capture_output=True, text=True, timeout=5)
        if out.returncode == 0:
            for line in out.stdout.strip().split("\n")[1:15]:
                parts = line.split(None, 3)
                if len(parts) < 4:
                    continue
                pid, cpu, mem, comm = parts
                cpu_val = float(cpu)
                if cpu_val < 5:
                    break
                name = comm.rsplit("/", 1)[-1]
                cpu_hogs.append({"pid": pid, "cpu": cpu, "mem": mem, "name": name,
                                 "cmdline": cmdlines.get(pid, "")})

        # Memory sorted
        out = subprocess.run(["ps", "-eo", "pid,pcpu,pmem,comm", "-m"],
                             capture_output=True, text=True, timeout=5)
        if out.returncode == 0:
            for line in out.stdout.strip().split("\n")[1:15]:
                parts = line.split(None, 3)
                if len(parts) < 4:
                    continue
                pid, cpu, mem, comm = parts
                mem_val = float(mem)
                if mem_val < 1.0:
                    break
                name = comm.rsplit("/", 1)[-1]
                mem_hogs.append({"pid": pid, "cpu": cpu, "mem": mem, "name": name,
                                 "cmdline": cmdlines.get(pid, "")})
    except (subprocess.TimeoutExpired, OSError):
        pass
    return cpu_hogs, mem_hogs


def _process_action(name: str, cmdline: str = "") -> str:
    """Suggest what to do about a resource-heavy process, using its full command line."""
    # System processes — specific advice, no kill command
    system = {
        "WindowServer": "System process — cannot be killed. Reduce windows/displays.",
        "kernel_task": "Thermal management — reduce workload, check ventilation.",
        "mds_stores": "Spotlight indexing — wait, or exclude folders in System Settings → Siri & Spotlight.",
        "mds": "Spotlight indexing — transient.",
        "fileproviderd": "Cloud sync (OneDrive/iCloud) — pause sync or reduce sync folders.",
        "trustd": "Certificate validation — transient, resolves after sync completes.",
        "XprotectService": "Security scan — transient, let it finish.",
        "mediaanalysisd": "Photo/video analysis — transient background task.",
        "bird": "iCloud sync daemon — pause iCloud or wait.",
        "launchd": "System init — cannot be killed.",
    }
    if name in system:
        return system[name]

    # Known third-party — specific advice
    third_party = {
        "OneDrive": "Pause in menu bar or reduce sync scope.",
        "Dropbox": "Pause in menu bar.",
        "Docker Desktop": "Check resource limits: Docker Desktop → Settings → Resources.",
        "prl_client_app": "Parallels VM — suspend or shut down the VM.",
    }
    for key, advice in third_party.items():
        if key.lower() in name.lower():
            return advice

    # Use command line to identify what the process is actually doing
    if cmdline:
        identity = _identify_from_cmdline(cmdline, name)
        if identity:
            return identity

    return f'<span class="action-cmd">kill {name}: kill -15 $(pgrep -f "{_esc(name)}")</span>'


def _identify_from_cmdline(cmdline: str, name: str) -> str:
    """Parse a command line and return a human-readable description + action."""
    cl = cmdline.lower()

    # Python processes — identify the script/module
    if "python" in name.lower():
        # uvicorn / gunicorn / fastapi
        if "uvicorn" in cl:
            module = cmdline.split("uvicorn")[-1].strip().split()[0] if "uvicorn" in cmdline else "?"
            return f'Web server: <code>{_esc(module)}</code> — <span class="action-cmd">kill -15 {name}</span>'
        # python -m module
        if " -m " in cmdline:
            module = cmdline.split(" -m ")[-1].strip().split()[0]
            return f'Module: <code>{_esc(module)}</code> — <span class="action-cmd">kill -15 {name}</span>'
        # python script.py
        for part in cmdline.split():
            if part.endswith(".py"):
                script = part.rsplit("/", 1)[-1]
                return f'Script: <code>{_esc(script)}</code> — <span class="action-cmd">kill -15 {name}</span>'
        # pip install
        if "pip" in cl:
            return f'pip operation — wait for it to finish.'

    # Node processes
    if "node" in name.lower():
        if "next" in cl:
            return 'Next.js dev server — <span class="action-cmd">kill -15 {}</span>'.format(name)
        if "vite" in cl:
            return 'Vite dev server — <span class="action-cmd">kill -15 {}</span>'.format(name)
        if "tsx" in cl or "ts-node" in cl:
            for part in cmdline.split():
                if part.endswith(".ts") or part.endswith(".tsx"):
                    script = part.rsplit("/", 1)[-1]
                    return f'TypeScript: <code>{_esc(script)}</code>'
        for part in cmdline.split():
            if part.endswith(".js"):
                script = part.rsplit("/", 1)[-1]
                return f'Script: <code>{_esc(script)}</code>'

    # Ruby
    if "ruby" in name.lower():
        if "rails" in cl:
            return 'Rails server'
        if "puma" in cl:
            return 'Puma web server'

    # Claude / AI tools
    if "claude" in cl:
        return 'Claude Code session'

    # Launchd services (run-daemon.sh, run-server.sh)
    if "run-daemon" in cl or "run-server" in cl:
        # Extract the directory to identify the service
        for part in cmdline.split():
            if "/" in part and ("run-daemon" in part or "run-server" in part):
                service = part.split("/")[-3] if part.count("/") >= 3 else part.rsplit("/", 1)[-1]
                return f'Daemon: <code>{_esc(service)}</code> — <span class="action-cmd">launchctl list | grep {_esc(service)}</span>'

    # Generic: show truncated command line so the user can at least see what it is
    short_cmd = cmdline[:80]
    if len(cmdline) > 80:
        short_cmd += "..."
    return f'<code style="font-size:11px;color:#475569">{_esc(short_cmd)}</code>'


def _mini_sparkline(values: list[float], width: int = 80, height: int = 16) -> str:
    """Tiny inline SVG sparkline for a process CPU history."""
    if not values or len(values) < 2:
        return '<span style="color:#94a3b8">—</span>'
    mn, mx = min(values), max(values)
    rng = mx - mn if mx != mn else 1
    points = []
    for i, v in enumerate(values):
        x = i / max(len(values) - 1, 1) * width
        y = height - ((v - mn) / rng * (height - 2)) - 1
        points.append(f"{x:.0f},{y:.0f}")
    return (f'<svg width="{width}" height="{height}" style="vertical-align:middle">'
            f'<polyline points="{" ".join(points)}" fill="none" stroke="#0e7490" stroke-width="1.5"/>'
            f'</svg>')


def _is_daemon(cmdline: str) -> bool:
    """Detect if a process is a background daemon/service vs a user-facing app."""
    cl = cmdline.lower()
    daemon_signals = [
        "launchd", "daemon", "run-server", "run-daemon", "uvicorn", "gunicorn",
        "celery", "worker", "cron", "/usr/sbin/", "/usr/libexec/",
        "com.apple.", "com.reeves.", "com.tosh.", "com.eidos", "com.helios",
        "-m ", "python3 -",  # scripts run as modules
    ]
    app_signals = [
        "/Applications/", ".app/Contents/MacOS/", "Electron", "iTerm",
        "Chrome", "Safari", "Firefox", "Cursor", "Xcode",
    ]
    for sig in app_signals:
        if sig.lower() in cl:
            return False
    for sig in daemon_signals:
        if sig in cl:
            return True
    # If it's in /usr/local, /opt/homebrew, or a repos directory, likely a daemon/script
    if any(p in cl for p in ["/repos-", "/opt/homebrew/", "/.local/", "/.venv/"]):
        return True
    return False


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ── Uptime helper ──

def _get_uptime() -> str:
    try:
        out = subprocess.run(["sysctl", "-n", "kern.boottime"], capture_output=True, text=True, timeout=5)
        boot_sec = int(out.stdout.split("sec = ")[1].split(",")[0])
        uptime_sec = int(datetime.now().timestamp()) - boot_sec
        days = uptime_sec // 86400
        hours = (uptime_sec % 86400) // 3600
        if days > 0:
            return f"{days}d {hours}h"
        return f"{hours}h {(uptime_sec % 3600) // 60}m"
    except Exception:
        return "?"


# ── BLUF generator ──

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
            "Shutdown Causes": f"{top_count} abnormal shutdown(s) detected — your Mac is not shutting down cleanly",
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
    if spikes:
        ongoing = [s for s in spikes if s.get("ongoing")]
        if ongoing:
            parts.append("a load spike is happening right now")
    return ". ".join(parts) + "." if parts else "Review the findings below."


# ── Score matrix ──

def _compute_matrix(report) -> dict:
    dimension_checks = {
        "stability": ["Crash Loops", "Kernel Panics", "Shutdown Causes"],
        "cpu": ["CPU Load"], "thermal": ["Thermal"], "memory": ["Memory Pressure"],
        "storage": ["Disk Health"], "services": ["Launch Agents"],
        "security": ["Security"], "infra": ["Dynamic Library Health", "Homebrew"],
        "network": ["Network"],
    }
    weights = {
        "stability": 3, "cpu": 3, "memory": 2, "thermal": 2,
        "storage": 2, "services": 2, "security": 1, "infra": 1, "network": 1,
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
    for dim, checks in dimension_checks.items():
        scores = [check_scores.get(c, 100) for c in checks]
        matrix[dim] = min(scores) if scores else 100
    weighted_sum = sum(matrix.get(d, 100) * w for d, w in weights.items())
    total_weight = sum(weights.values())
    overall = round(weighted_sum / total_weight)
    grade = "A" if overall >= 90 else "B" if overall >= 75 else "C" if overall >= 50 else "D" if overall >= 25 else "F"
    matrix["_overall"] = overall
    matrix["_grade"] = grade
    return matrix


def _pick_focus(criticals, warnings, spikes, offenders) -> list[str]:
    focus = []
    if criticals:
        by_check: dict[str, list] = {}
        for c in criticals:
            by_check.setdefault(c["check"], []).append(c)
        for check, items in sorted(by_check.items(), key=lambda x: -len(x[1])):
            fix = items[0].get("fix", "")[:80]
            focus.append(f"FIX: {check} — {len(items)} critical issue(s). {fix}")
            if len(focus) >= 2:
                break
    if spikes:
        ongoing = [s for s in spikes if s.get("ongoing")]
        if ongoing:
            procs = ", ".join(p[1] for p in ongoing[0].get("top_processes", []))
            focus.append(f"NOW: Active load spike (peak {ongoing[0]['peak_load']:.0f}x) — {procs}")
    if warnings and len(focus) < 3:
        focus.append(f"REVIEW: {len(warnings)} warning(s) — {warnings[0]['summary'][:60]}")
    if offenders and len(focus) < 3:
        top = offenders[0]
        focus.append(f"WATCH: {top['name']} appears in top-CPU {top['appearances']}x (peak {top['peak_cpu']}%)")
    return focus[:3]


# ── Main report generator ──

def generate_html_report(vitals_minutes: int = 60) -> str:
    report = run_all_checks(parallel=True)
    vitals = analyze_vitals(minutes=vitals_minutes)
    history = read_recent(10)
    samples = read_vitals(minutes=vitals_minutes)
    cores = os.cpu_count() or 8
    info = report.mac_info
    uptime = _get_uptime()

    criticals, warnings, infos = [], [], []
    for r in report.results:
        for f in r.findings:
            entry = {"check": r.name, "summary": f.summary, "fix": f.fix,
                     "details": f.details, "severity": f.severity.value}
            if f.severity.value == "critical":
                criticals.append(entry)
            elif f.severity.value == "warning":
                warnings.append(entry)
            elif f.severity.value == "info":
                infos.append(entry)

    matrix = _compute_matrix(report)
    overall = matrix.pop("_overall", 0)
    grade = matrix.pop("_grade", "?")

    spikes = vitals.get("load", {}).get("spikes", [])
    offenders = vitals.get("worst_offenders", [])

    trend = None
    if len(history) >= 3:
        recent_c = sum(e.get("counts", {}).get("critical", 0) for e in history[-3:]) / 3
        older_c = sum(e.get("counts", {}).get("critical", 0) for e in history[:3]) / 3
        trend = "improving" if recent_c < older_c else "degrading" if recent_c > older_c else "stable"

    focus = _pick_focus(criticals, warnings, spikes, offenders)
    grade_color = {"A": "#22c55e", "B": "#22c55e", "C": "#ca8a04", "D": "#ef4444", "F": "#ef4444"}.get(grade, "#94a3b8")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    bluf_text = _generate_bluf(criticals, warnings, infos, spikes)

    # Collect all knowledge topics referenced
    all_topics: set[str] = set()
    for item in criticals + warnings:
        all_topics.update(match_topics(item["summary"], item["check"]))

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>apple-a-day — {grade} ({overall}/100)</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: #f8fafc; color: #1e293b; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; padding: 24px; max-width: 860px; margin: 0 auto; font-size: 14px; line-height: 1.5; }}
  code, .mono {{ font-family: 'SF Mono', 'Fira Code', monospace; font-size: 12px; }}
  h1 {{ font-size: 20px; font-weight: 700; margin-bottom: 4px; }}
  h2 {{ font-size: 15px; font-weight: 600; color: #475569; margin: 28px 0 12px; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px; }}
  .header {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px 24px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }}
  .header-left h1 {{ color: #0f172a; }}
  .header-left .subtitle {{ color: #64748b; font-size: 13px; margin-top: 4px; }}
  .bluf {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px 24px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }}
  .bluf-label {{ font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: #94a3b8; margin-bottom: 6px; }}
  .bluf-summary {{ font-size: 15px; line-height: 1.6; }}
  .bluf-counts {{ display: flex; gap: 12px; margin-top: 12px; font-size: 12px; }}
  .bluf-count {{ padding: 3px 12px; border-radius: 4px; font-weight: 600; }}
  .bluf-count.crit {{ background: #fef2f2; color: #dc2626; }}
  .bluf-count.warn {{ background: #fffbeb; color: #92400e; }}
  .bluf-count.info {{ background: #eff6ff; color: #1e40af; }}
  .sysinfo {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 12px; margin-bottom: 20px; }}
  .sysinfo-item {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px 16px; text-align: center; }}
  .sysinfo-val {{ font-size: 18px; font-weight: 700; color: #0f172a; font-family: 'SF Mono', monospace; }}
  .sysinfo-label {{ font-size: 11px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 2px; }}
  .card {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px 20px; margin: 12px 0; box-shadow: 0 1px 3px rgba(0,0,0,0.04); }}
  .matrix-row {{ display: flex; align-items: center; margin: 6px 0; }}
  .matrix-label {{ width: 90px; font-size: 13px; color: #475569; }}
  .matrix-val {{ font-size: 13px; color: #64748b; margin-left: 8px; width: 30px; text-align: right; font-family: 'SF Mono', monospace; }}
  .finding {{ padding: 10px 0; border-bottom: 1px solid #f1f5f9; }}
  .finding:last-child {{ border-bottom: none; }}
  .finding-fix {{ font-size: 13px; color: #475569; margin-top: 6px; padding-left: 16px; border-left: 2px solid #e2e8f0; }}
  .offender {{ display: flex; align-items: center; margin: 6px 0; font-size: 13px; }}
  .offender-name {{ width: 200px; color: #1e293b; font-family: 'SF Mono', monospace; }}
  .focus-box {{ background: #fff; border: 2px solid #0284c7; border-radius: 8px; padding: 20px; margin: 20px 0; }}
  .focus-box h2 {{ border-bottom: none; margin: 0 0 12px; color: #0f172a; font-size: 16px; }}
  .focus-item {{ padding: 6px 0; font-size: 14px; }}
  .focus-item .tag {{ font-weight: 700; }}
  .focus-item .tag-fix {{ color: #dc2626; }}
  .focus-item .tag-now {{ color: #d97706; }}
  .focus-item .tag-review {{ color: #92400e; }}
  .focus-item .tag-watch {{ color: #0284c7; }}
  .spike {{ background: #fef2f2; border-left: 3px solid #ef4444; padding: 8px 12px; margin: 6px 0; font-size: 13px; border-radius: 0 4px 4px 0; }}
  .spark-container {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px 20px; }}
  .spark-stats {{ display: flex; gap: 24px; margin-top: 8px; font-size: 12px; color: #64748b; font-family: 'SF Mono', monospace; }}
  .spark-stats b {{ color: #1e293b; }}
  .knowledge {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; margin: 8px 0; font-size: 13px; }}
  .knowledge summary {{ padding: 8px 12px; cursor: pointer; color: #0284c7; font-weight: 500; }}
  .knowledge summary:hover {{ background: #f1f5f9; }}
  .knowledge .k-section {{ padding: 6px 12px 6px 24px; color: #475569; line-height: 1.6; }}
  .knowledge .k-section b {{ color: #1e293b; }}
  .tradeoff {{ background: #fffbeb; border: 1px solid #fde68a; border-radius: 6px; padding: 12px 16px; margin: 8px 0; font-size: 13px; }}
  .tradeoff-gain {{ color: #16a34a; }}
  .tradeoff-lose {{ color: #dc2626; }}
  .trend-card {{ font-size: 15px; }}
  .trend-up {{ color: #16a34a; }}
  .trend-down {{ color: #dc2626; }}
  .trend-flat {{ color: #64748b; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; table-layout: fixed; }}
  th {{ text-align: left; padding: 8px 12px; color: #475569; font-weight: 600; border-bottom: 2px solid #e2e8f0; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; }}
  td {{ padding: 6px 12px; border-bottom: 1px solid #f1f5f9; vertical-align: top; word-wrap: break-word; overflow-wrap: break-word; }}
  tr:hover {{ background: #f8fafc; }}
  .mono {{ font-family: 'SF Mono', monospace; font-size: 12px; }}
  code {{ word-break: break-all; }}
  .action-cmd {{ background: #f1f5f9; padding: 2px 8px; border-radius: 3px; font-family: 'SF Mono', monospace; font-size: 11px; color: #334155; display: inline-block; margin-top: 2px; word-break: break-all; }}
  .finding-fix {{ word-wrap: break-word; overflow-wrap: break-word; }}
  .matrix-issue {{ font-size: 12px; color: #64748b; margin-left: 8px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .matrix-row {{ flex-wrap: nowrap; overflow: hidden; }}
  footer {{ margin-top: 32px; padding-top: 16px; border-top: 1px solid #e2e8f0; font-size: 11px; color: #94a3b8; text-align: center; }}
</style>
</head>
<body>

<div class="header">
  <div class="header-left">
    <h1>apple-a-day health report</h1>
    <div class="subtitle">macOS {info.get('os_version', '?')} · {info.get('cpu', '?')} · {now_str}</div>
  </div>
  <div>{_donut_svg(overall, grade, grade_color)}</div>
</div>

<div class="bluf">
  <div class="bluf-label">Bottom Line Up Front</div>
  <div class="bluf-summary">{bluf_text}</div>
  <div class="bluf-counts">
    <span class="bluf-count crit">{len(criticals)} critical</span>
    <span class="bluf-count warn">{len(warnings)} warning</span>
    <span class="bluf-count info">{len(infos)} info</span>
  </div>
</div>
"""

    # ── System Info strip ──
    swap_mb = vitals.get("swap", {}).get("current_mb")
    swap_str = f"{swap_mb / 1024:.1f} GB" if swap_mb else "?"
    html += f"""<div class="sysinfo">
  <div class="sysinfo-item"><div class="sysinfo-val">{info.get('memory_gb', '?')} GB</div><div class="sysinfo-label">RAM</div></div>
  <div class="sysinfo-item"><div class="sysinfo-val">{swap_str}</div><div class="sysinfo-label">Swap</div></div>
  <div class="sysinfo-item"><div class="sysinfo-val">{cores}</div><div class="sysinfo-label">Cores</div></div>
  <div class="sysinfo-item"><div class="sysinfo-val">{uptime}</div><div class="sysinfo-label">Uptime</div></div>
</div>
"""

    # ── Focus box ──
    if focus:
        html += '<div class="focus-box"><h2>Focus</h2>\n'
        for i, f in enumerate(focus, 1):
            tag = f.split(":")[0] if ":" in f else "ACTION"
            rest = f.split(":", 1)[1].strip() if ":" in f else f
            html += f'<div class="focus-item">{i}. <span class="tag tag-{tag.lower()}">{tag}</span> {_esc(rest)}</div>\n'
        html += '</div>\n'

    # ── Health Matrix (with worst finding per dimension) ──
    # Map dimensions to check names for finding lookup
    dim_check_map = {
        "stability": ["Crash Loops", "Kernel Panics", "Shutdown Causes"],
        "cpu": ["CPU Load"], "thermal": ["Thermal"], "memory": ["Memory Pressure"],
        "storage": ["Disk Health"], "services": ["Launch Agents"],
        "security": ["Security"], "infra": ["Dynamic Library Health", "Homebrew"],
        "network": ["Network"],
    }
    # Find worst finding per dimension
    dim_worst: dict[str, str] = {}
    all_findings = criticals + warnings
    for dim, checks in dim_check_map.items():
        for item in all_findings:
            if item["check"] in checks:
                dim_worst[dim] = item["summary"]
                break

    html += '<h2>Health Matrix</h2>\n'
    for dim, label in [("stability", "Stability"), ("cpu", "CPU"), ("thermal", "Thermal"),
                       ("memory", "Memory"), ("storage", "Storage"), ("services", "Services"),
                       ("security", "Security"), ("infra", "Infra"), ("network", "Network")]:
        val = matrix.get(dim, 100)
        issue = dim_worst.get(dim, "")
        issue_html = f'<span class="matrix-issue">{_esc(issue[:60])}</span>' if issue else ""
        html += f'<div class="matrix-row"><span class="matrix-label">{label}</span>{_bar_svg(val)}<span class="matrix-val">{val}</span>{issue_html}</div>\n'

    # ── Load Sparkline ──
    if samples:
        load_values = [s["load"][0] for s in samples if "load" in s]
        if load_values:
            peak = max(load_values)
            avg = sum(load_values) / len(load_values)
            html += '<h2>Load History</h2>\n<div class="spark-container">\n'
            html += _sparkline_svg(load_values, width=780, height=70)
            html += f'<div class="spark-stats"><span>peak: <b>{peak:.0f}</b></span><span>avg: <b>{avg:.1f}</b></span><span>cores: <b>{cores}</b></span><span>samples: <b>{len(load_values)}</b></span></div>\n'
            html += '</div>\n'
            if spikes:
                for s in spikes[:3]:
                    ongoing = ' <span style="color:#ef4444;font-weight:700">ONGOING</span>' if s.get("ongoing") else ""
                    procs = ", ".join(f"{p[1]} ({p[0]}%)" for p in s.get("top_processes", [])[:3])
                    html += f'<div class="spike">▲ spike peak <b>{s["peak_load"]:.0f}x</b> — {_esc(procs)}{ongoing}</div>\n'
            html += _knowledge_card(["load_average"])

    # ── Sustained Pressure (from vitals time-series) ──
    if offenders:
        sustained = [o for o in offenders if o.get("sustained")]
        transient = [o for o in offenders if not o.get("sustained")]

        if sustained:
            html += '<h2>Sustained Pressure (long-running load)</h2>\n<div class="card">\n'
            html += '<div style="font-size:12px;color:#64748b;margin-bottom:8px">Processes consuming CPU across >50% of the monitoring window. These cause crashes, not spikes.</div>\n'
            max_total = max(o["total_cpu"] for o in sustained) if sustained else 1
            html += '<table><tr><th>Process</th><th style="width:200px">Cumulative CPU</th><th>Avg CPU</th><th>Present</th><th>Pattern</th></tr>\n'
            for o in sustained[:7]:
                bar_w = int(o["total_cpu"] / max(max_total, 1) * 140)
                color = "#ef4444" if o["avg_cpu"] > 30 else "#ca8a04" if o["avg_cpu"] > 10 else "#0284c7"
                bar = f'<div style="display:flex;align-items:center;gap:6px"><div style="width:{bar_w}px;height:12px;background:{color};border-radius:2px"></div><span class="mono">{o["total_cpu"]:.0f}%·s</span></div>'
                spark = _mini_sparkline(o.get("cpu_series", []))
                html += f'<tr><td class="mono">{_esc(o["name"])}</td><td>{bar}</td><td class="mono">{o["avg_cpu"]}%</td><td>{o["presence_pct"]:.0f}%</td><td>{spark}</td></tr>\n'
            html += '</table></div>\n'
            html += _knowledge_card(["load_average"])

        if transient:
            html += '<h2>Transient Load (spikes)</h2>\n<div class="card">\n'
            html += '<div style="font-size:12px;color:#64748b;margin-bottom:8px">Processes that appeared briefly at high CPU. Usually normal (builds, scans, syncs).</div>\n'
            max_peak = max(o["peak_cpu"] for o in transient[:7])
            html += '<table><tr><th>Process</th><th style="width:200px">Peak CPU</th><th>Seen</th><th>Pattern</th></tr>\n'
            for o in transient[:5]:
                bar_w = int(o["peak_cpu"] / max(max_peak, 1) * 140)
                color = "#ca8a04" if o["peak_cpu"] > 30 else "#0284c7"
                bar = f'<div style="display:flex;align-items:center;gap:6px"><div style="width:{bar_w}px;height:12px;background:{color};border-radius:2px"></div><span class="mono">{o["peak_cpu"]}%</span></div>'
                spark = _mini_sparkline(o.get("cpu_series", []))
                html += f'<tr><td class="mono">{_esc(o["name"])}</td><td>{bar}</td><td>{o["appearances"]}x</td><td>{spark}</td></tr>\n'
            html += '</table></div>\n'

    # ── Live Process Tables (CPU, Memory) ──
    cpu_hogs, mem_hogs = _get_live_process_tables()

    # Split processes into daemons vs regular
    daemon_hogs = [p for p in cpu_hogs if _is_daemon(p.get("cmdline", ""))]
    app_cpu_hogs = [p for p in cpu_hogs if not _is_daemon(p.get("cmdline", ""))]

    if daemon_hogs:
        max_cpu_d = max(float(p["cpu"]) for p in daemon_hogs)
        html += '<h2>Daemon Hogs (background services)</h2>\n<div class="card">\n'
        html += '<div style="font-size:12px;color:#64748b;margin-bottom:8px">These are launchd-managed services or background scripts running without a visible app window.</div>\n'
        html += '<table><tr><th>Service</th><th style="width:200px">CPU %</th><th>What it is</th></tr>\n'
        for p in daemon_hogs:
            cpu_val = float(p["cpu"])
            bar_w = int(cpu_val / max(max_cpu_d, 1) * 140)
            color = "#ef4444" if cpu_val > 50 else "#ca8a04" if cpu_val > 20 else "#0284c7"
            bar = f'<div style="display:flex;align-items:center;gap:6px"><div style="width:{bar_w}px;height:12px;background:{color};border-radius:2px"></div><span class="mono">{p["cpu"]}%</span></div>'
            identity = _process_action(p["name"], p.get("cmdline", ""))
            html += f'<tr><td class="mono">{_esc(p["name"])} <span style="color:#94a3b8">({p["pid"]})</span></td><td>{bar}</td><td>{identity}</td></tr>\n'
        html += '</table></div>\n'

    if app_cpu_hogs:
        max_cpu = max(float(p["cpu"]) for p in app_cpu_hogs)
        html += '<h2>CPU Hogs (right now)</h2>\n<div class="card">\n'
        html += '<table><tr><th>Process</th><th style="width:200px">CPU %</th><th>MEM %</th><th>What it is</th></tr>\n'
        for p in app_cpu_hogs:
            cpu_val = float(p["cpu"])
            bar_w = int(cpu_val / max(max_cpu, 1) * 140)
            color = "#ef4444" if cpu_val > 50 else "#ca8a04" if cpu_val > 20 else "#0284c7"
            bar = f'<div style="display:flex;align-items:center;gap:6px"><div style="width:{bar_w}px;height:12px;background:{color};border-radius:2px"></div><span class="mono">{p["cpu"]}%</span></div>'
            identity = _process_action(p["name"], p.get("cmdline", ""))
            html += f'<tr><td class="mono">{_esc(p["name"])} <span style="color:#94a3b8">({p["pid"]})</span></td><td>{bar}</td><td class="mono">{p["mem"]}%</td><td>{identity}</td></tr>\n'
        html += '</table></div>\n'

    if mem_hogs:
        max_mem = max(float(p["mem"]) for p in mem_hogs)
        html += '<h2>Memory Hogs (right now)</h2>\n<div class="card">\n'
        html += '<table><tr><th>Process</th><th style="width:200px">MEM %</th><th>CPU %</th><th>What it is</th></tr>\n'
        for p in mem_hogs:
            mem_val = float(p["mem"])
            bar_w = int(mem_val / max(max_mem, 1) * 140)
            color = "#ef4444" if mem_val > 10 else "#ca8a04" if mem_val > 5 else "#0284c7"
            bar = f'<div style="display:flex;align-items:center;gap:6px"><div style="width:{bar_w}px;height:12px;background:{color};border-radius:2px"></div><span class="mono">{p["mem"]}%</span></div>'
            identity = _process_action(p["name"], p.get("cmdline", ""))
            html += f'<tr><td class="mono">{_esc(p["name"])} <span style="color:#94a3b8">({p["pid"]})</span></td><td>{bar}</td><td class="mono">{p["cpu"]}%</td><td>{identity}</td></tr>\n'
        html += '</table></div>\n'

    # ── Critical Issues ──
    if criticals:
        html += f'<h2 style="color:#dc2626">Critical Issues ({len(criticals)})</h2>\n<div class="card">\n'
        by_check: dict[str, list] = {}
        for c in criticals:
            by_check.setdefault(c["check"], []).append(c)
        topics_shown: set[str] = set()
        for check, items in sorted(by_check.items(), key=lambda x: -len(x[1])):
            html += f'<div class="finding">{_sev_badge("critical")} <b>{_esc(check)}</b> — {len(items)} issue(s)\n'
            for item in items[:5]:
                html += f'<div style="margin-left:16px;font-size:13px;color:#334155;margin-top:4px">{_esc(item["summary"])}</div>\n'
            if len(items) > 5:
                html += f'<div style="margin-left:16px;font-size:12px;color:#64748b">...and {len(items) - 5} more</div>\n'
            if items[0].get("fix"):
                html += f'<div class="finding-fix">→ {_esc(items[0]["fix"])}</div>\n'
            # Knowledge cards for this check (show once per topic)
            check_topics = match_topics(items[0]["summary"], check)
            new_topics = [t for t in check_topics if t not in topics_shown]
            if new_topics:
                html += _knowledge_card(new_topics)
                topics_shown.update(new_topics)
            html += '</div>\n'
        html += '</div>\n'

    # ── Warnings with trade-off framing ──
    if warnings:
        html += f'<h2 style="color:#92400e">Warnings ({len(warnings)})</h2>\n<div class="card">\n'
        topics_shown_w: set[str] = set()
        for w_item in warnings:
            html += f'<div class="finding">{_sev_badge("warning")} {_esc(w_item["summary"])}\n'
            if w_item.get("fix"):
                html += f'<div class="finding-fix">→ {_esc(w_item["fix"])}</div>\n'
            # Trade-off framing for actionable warnings
            tradeoff = _get_tradeoff(w_item)
            if tradeoff:
                html += f'<div class="tradeoff"><span class="tradeoff-gain">Gain:</span> {_esc(tradeoff["gain"])}<br><span class="tradeoff-lose">Lose:</span> {_esc(tradeoff["lose"])}</div>\n'
            # Knowledge card
            w_topics = match_topics(w_item["summary"], w_item["check"])
            new_w = [t for t in w_topics if t not in topics_shown_w]
            if new_w:
                html += _knowledge_card(new_w)
                topics_shown_w.update(new_w)
            html += '</div>\n'
        html += '</div>\n'

    # ── App Cleanup Scatterplot ──
    from .checks.cleanup import _find_stale_apps
    stale_apps = _find_stale_apps()
    if stale_apps:
        html += '<h2>App Cleanup Analysis</h2>\n<div class="card">\n'
        html += '<div style="font-size:13px;color:#475569;margin-bottom:8px">Apps plotted by size (impact) vs. time since last use. Top-right quadrant = high impact, rarely used — best removal candidates.</div>\n'
        html += _cleanup_scatterplot(stale_apps)
        # Companion table — actionable list
        remove_candidates = [a for a in stale_apps if a.get("days_ago", 0) > 90]
        if remove_candidates:
            max_size_rc = max(a.get("size_mb", 1) for a in remove_candidates[:10])
            html += '<table style="margin-top:12px"><tr><th>App</th><th style="width:200px">Size</th><th>Last Used</th><th>Action</th></tr>\n'
            for a in remove_candidates[:10]:
                size = a.get("size_mb", 0)
                size_str = f"{size} MB" if size < 1024 else f"{size / 1024:.1f} GB"
                bar_w = int(size / max(max_size_rc, 1) * 140)
                color = "#ef4444" if size > 500 else "#ca8a04" if size > 100 else "#0284c7"
                bar = f'<div style="display:flex;align-items:center;gap:6px"><div style="width:{bar_w}px;height:12px;background:{color};border-radius:2px"></div><span class="mono">{size_str}</span></div>'
                name = _esc(a["name"])
                html += f'<tr><td>{name}</td><td>{bar}</td><td>{a.get("last_used", "?")}</td>'
                html += f'<td><span class="action-cmd">sudo rm -rf "/Applications/{name}.app"</span></td></tr>\n'
            html += '</table>\n'
        html += '</div>\n'
        html += _knowledge_card(["orphaned_agent"])

    # ── Info ──
    if infos:
        html += f'<h2>Info ({len(infos)})</h2>\n<div class="card">\n'
        for item in infos[:8]:
            html += f'<div class="finding" style="color:#475569">{_sev_badge("info")} {_esc(item["summary"])}</div>\n'
        if len(infos) > 8:
            html += f'<div style="color:#64748b;font-size:12px;padding:8px 0">...and {len(infos) - 8} more</div>\n'
        html += '</div>\n'

    # ── Trend ──
    if trend:
        arrow = {"improving": ("↑ improving", "trend-up"), "degrading": ("↓ degrading", "trend-down"),
                 "stable": ("→ stable", "trend-flat")}.get(trend, ("?", ""))
        html += f'<h2>Trend</h2>\n<div class="card trend-card"><span class="{arrow[1]}" style="font-size:16px">{arrow[0]}</span></div>\n'

    html += f"""
<footer>apple-a-day v0.2.0 · {now_str} · {report.duration_ms}ms</footer>
</body></html>"""
    return html


def open_report(vitals_minutes: int = 60) -> Path:
    html = generate_html_report(vitals_minutes=vitals_minutes)
    report_dir = Path.home() / ".config" / "eidos" / "aad-logs"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "report.html"
    report_path.write_text(html)
    webbrowser.open(f"file://{report_path}")
    return report_path


# ── Trade-off framing ──

def _get_tradeoff(finding: dict) -> dict[str, str] | None:
    """Return gain/lose framing for actionable findings."""
    summary = finding["summary"].lower()
    check = finding["check"]

    if "swap" in summary:
        return {
            "gain": "Faster app switching, no more random freezes, reduced SSD wear",
            "lose": "Need to close some apps or reboot — temporary disruption",
        }
    if "disk" in check.lower() and ("full" in summary or "free" in summary):
        return {
            "gain": "Faster writes, swap can grow when needed, macOS updates work again",
            "lose": "Time spent cleaning up files — run the cleanup suggestions above",
        }
    if "crash" in summary and "loop" not in summary:
        return {
            "gain": "Fewer background crashes, cleaner logs, less noise",
            "lose": "May need to reinstall or update the crashing app",
        }
    if "orphaned" in summary:
        return {
            "gain": "Fewer wasted process spawns, cleaner launchd, less log noise",
            "lose": "Nothing — these agents serve no purpose, their app is already gone",
        }
    if "outdated" in summary and "homebrew" in check.lower():
        return {
            "gain": "Security patches, bug fixes, compatibility with newer tools",
            "lose": "Possible breaking changes — review changelogs before upgrading all at once",
        }
    if "crash-looping" in summary or "crash loop" in summary:
        return {
            "gain": "CPU freed from restart cycles, fewer kernel panic triggers",
            "lose": "The service stops running — check if anything depends on it first",
        }
    return None
