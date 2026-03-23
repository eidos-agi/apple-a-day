"""Generate a focused health report with ASCII graphs.

Designed for agents and humans who want the "so what" — not raw findings,
but a prioritized view of what to focus on, with visual indicators.
"""

import os
from datetime import datetime

from .log import read_recent
from .runner import run_all_checks
from .vitals import analyze_vitals, read_vitals

# ANSI
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"
WHITE = "\033[37m"
BG_RED = "\033[41m"
BG_YELLOW = "\033[43m"
BG_GREEN = "\033[42m"


def _c(text: str, *codes: str) -> str:
    prefix = "".join(codes)
    return f"{prefix}{text}{RESET}"


def _bar(value: int, max_val: int = 100, width: int = 25, fill: str = "█", empty: str = "░") -> str:
    """Render a horizontal bar chart segment."""
    filled = int(value / max_val * width)
    return fill * filled + empty * (width - filled)


def _sparkline(values: list[float], width: int = 40) -> str:
    """Render a sparkline from a list of values."""
    if not values:
        return ""
    blocks = " ▁▂▃▄▅▆▇█"
    mn, mx = min(values), max(values)
    rng = mx - mn if mx != mn else 1

    # Downsample if too many values
    if len(values) > width:
        step = len(values) / width
        sampled = [values[int(i * step)] for i in range(width)]
    else:
        sampled = values

    return "".join(blocks[min(8, int((v - mn) / rng * 8))] for v in sampled)


def generate_report(as_json: bool = False, vitals_minutes: int = 60) -> str | dict:
    """Run checks + analyze vitals, produce a focused report."""
    report = run_all_checks(parallel=True)
    vitals = analyze_vitals(minutes=vitals_minutes)
    history = read_recent(10)

    # Collect all findings by severity
    criticals = []
    warnings = []
    infos = []
    for r in report.results:
        for f in r.findings:
            entry = {"check": r.name, "summary": f.summary, "fix": f.fix, "details": f.details}
            if f.severity.value == "critical":
                criticals.append(entry)
            elif f.severity.value == "warning":
                warnings.append(entry)
            elif f.severity.value == "info":
                infos.append(entry)

    # Score matrix from this run
    matrix = _compute_matrix(report)
    overall = matrix.pop("_overall", 0)
    grade = matrix.pop("_grade", "?")

    # Vitals summary
    load_data = vitals.get("load", {})
    spikes = load_data.get("spikes", [])
    offenders = vitals.get("worst_offenders", [])

    # Trend
    trend_direction = None
    if len(history) >= 3:
        recent_crits = sum(e.get("counts", {}).get("critical", 0) for e in history[-3:]) / 3
        older_crits = sum(e.get("counts", {}).get("critical", 0) for e in history[:3]) / 3
        if recent_crits < older_crits:
            trend_direction = "improving"
        elif recent_crits > older_crits:
            trend_direction = "degrading"
        else:
            trend_direction = "stable"

    if as_json:
        return {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "grade": grade,
            "score": overall,
            "matrix": matrix,
            "criticals": criticals,
            "warnings": warnings,
            "infos": infos,
            "vitals": {
                "samples": vitals.get("samples", 0),
                "spikes": spikes,
                "offenders": offenders[:5],
            },
            "trend": trend_direction,
            "focus": _pick_focus(criticals, warnings, spikes, offenders),
        }

    return _render_ansi(
        overall, grade, matrix, criticals, warnings, infos,
        load_data, spikes, offenders, trend_direction, vitals, report,
    )


def _compute_matrix(report) -> dict:
    """Compute health score matrix from a report."""
    dimension_checks = {
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

    if overall >= 90:
        grade = "A"
    elif overall >= 75:
        grade = "B"
    elif overall >= 50:
        grade = "C"
    elif overall >= 25:
        grade = "D"
    else:
        grade = "F"

    matrix["_overall"] = overall
    matrix["_grade"] = grade
    return matrix


def _pick_focus(criticals, warnings, spikes, offenders) -> list[str]:
    """Pick the top 3 things to focus on, in priority order."""
    focus = []

    if criticals:
        # Group by check
        by_check = {}
        for c in criticals:
            by_check.setdefault(c["check"], []).append(c)
        for check, items in sorted(by_check.items(), key=lambda x: -len(x[1])):
            focus.append(f"FIX: {check} — {len(items)} critical issue(s). {items[0].get('fix', '')[:80]}")
            if len(focus) >= 2:
                break

    if spikes:
        ongoing = [s for s in spikes if s.get("ongoing")]
        if ongoing:
            focus.append(f"NOW: Active load spike (peak {ongoing[0]['peak_load']:.0f}x) — "
                         f"{', '.join(p[1] for p in ongoing[0].get('top_processes', []))}")

    if warnings and len(focus) < 3:
        focus.append(f"REVIEW: {len(warnings)} warning(s) — {warnings[0]['summary'][:60]}")

    if offenders and len(focus) < 3:
        top = offenders[0]
        focus.append(f"WATCH: {top['name']} appears in top-CPU {top['appearances']}x (peak {top['peak_cpu']}%)")

    return focus[:3]


def _render_ansi(overall, grade, matrix, criticals, warnings, _infos,
                 _load_data, spikes, offenders, trend, _vitals, report) -> str:
    """Render the report as ANSI text with ASCII graphs."""
    lines = []
    cores = os.cpu_count() or 8
    w = 72

    # ── Header ──
    grade_color = {
        "A": GREEN, "B": GREEN, "C": YELLOW, "D": RED, "F": RED
    }.get(grade, WHITE)

    lines.append("")
    lines.append(_c("╔" + "═" * (w - 2) + "╗", DIM))
    title = f"  apple-a-day health report"
    grade_str = f"{grade} ({overall}/100)"
    pad = w - 4 - len(title) - len(grade_str)
    lines.append(_c("║", DIM) + _c(title, BOLD) + " " * pad + _c(grade_str, grade_color, BOLD) + _c("  ║", DIM))

    info = report.mac_info
    subtitle = f"  macOS {info.get('os_version', '?')} | {info.get('cpu', '?')} | {info.get('memory_gb', '?')} GB RAM"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    pad2 = w - 4 - len(subtitle) - len(now_str)
    lines.append(_c("║", DIM) + _c(subtitle, DIM) + " " * pad2 + _c(now_str, DIM) + _c("  ║", DIM))
    lines.append(_c("╚" + "═" * (w - 2) + "╝", DIM))
    lines.append("")

    # ── Health Matrix (bar chart) ──
    lines.append(_c("── Health Matrix ", BOLD) + _c("─" * (w - 18), DIM))
    lines.append("")

    dim_labels = {
        "stability": "Stability ",
        "cpu":       "CPU       ",
        "thermal":   "Thermal   ",
        "memory":    "Memory    ",
        "storage":   "Storage   ",
        "services":  "Services  ",
        "security":  "Security  ",
        "infra":     "Infra     ",
        "network":   "Network   ",
    }

    for dim, label in dim_labels.items():
        val = matrix.get(dim, 100)
        color = GREEN if val >= 80 else YELLOW if val >= 50 else RED
        bar = _bar(val, 100, 30)
        lines.append(f"  {label} {_c(bar, color)} {val}")

    lines.append("")

    # ── Load Sparkline (if vitals data) ──
    samples = read_vitals(minutes=60)
    if samples:
        load_values = [s["load"][0] for s in samples if "load" in s]
        if load_values:
            lines.append(_c("── Load History (last hour) ", BOLD) + _c("─" * (w - 28), DIM))
            spark = _sparkline(load_values, width=50)
            peak = max(load_values)
            avg = sum(load_values) / len(load_values)
            lines.append(f"  {_c(spark, CYAN)}  peak:{peak:.0f} avg:{avg:.0f} cores:{cores}")

            if spikes:
                for s in spikes[:3]:
                    ongoing = _c(" ONGOING", RED, BOLD) if s.get("ongoing") else ""
                    procs = ", ".join(f"{p[1]}" for p in s.get("top_processes", [])[:3])
                    lines.append(f"  {_c('▲', RED)} spike peak {s['peak_load']:.0f}x — {procs}{ongoing}")

            lines.append("")

    # ── Top Offenders (if vitals data) ──
    if offenders:
        lines.append(_c("── Top Resource Offenders ", BOLD) + _c("─" * (w - 26), DIM))
        max_appearances = max(o["appearances"] for o in offenders[:7])
        for o in offenders[:7]:
            bar_w = int(o["appearances"] / max(max_appearances, 1) * 20)
            bar = "▓" * bar_w + "░" * (20 - bar_w)
            lines.append(f"  {o['name']:25s} {_c(bar, CYAN)} {o['appearances']}x  peak {o['peak_cpu']}%")
        lines.append("")

    # ── Critical Issues ──
    if criticals:
        lines.append(_c("── Critical Issues ", RED, BOLD) + _c("─" * (w - 20), RED))
        by_check = {}
        for c in criticals:
            by_check.setdefault(c["check"], []).append(c)
        for check, items in sorted(by_check.items(), key=lambda x: -len(x[1])):
            lines.append(f"  {_c('✗', RED)} {_c(check, RED, BOLD)}: {len(items)} issue(s)")
            for item in items[:3]:
                lines.append(f"    {item['summary'][:65]}")
            if len(items) > 3:
                lines.append(_c(f"    ... and {len(items) - 3} more", DIM))
            if items[0].get("fix"):
                lines.append(f"    {_c('→', DIM)} {items[0]['fix'][:65]}")
        lines.append("")

    # ── Warnings ──
    if warnings:
        lines.append(_c("── Warnings ", YELLOW, BOLD) + _c("─" * (w - 13), YELLOW))
        for w_item in warnings[:6]:
            lines.append(f"  {_c('⚠', YELLOW)} {w_item['summary'][:65]}")
            if w_item.get("fix"):
                lines.append(f"    {_c('→', DIM)} {w_item['fix'][:65]}")
        if len(warnings) > 6:
            lines.append(_c(f"  ... and {len(warnings) - 6} more", DIM))
        lines.append("")

    # ── Trend ──
    if trend:
        arrow = {"improving": _c("↑ improving", GREEN), "degrading": _c("↓ degrading", RED),
                 "stable": _c("→ stable", DIM)}.get(trend, "")
        lines.append(_c("── Trend ", BOLD) + _c("─" * (w - 10), DIM))
        lines.append(f"  Direction: {arrow}")
        lines.append("")

    # ── Focus (top 3 actions) ──
    focus = _pick_focus(criticals, warnings, spikes, offenders)
    if focus:
        lines.append(_c("╔" + "═" * (w - 2) + "╗", BOLD))
        lines.append(_c("║", BOLD) + _c("  FOCUS", BOLD) + " " * (w - 9) + _c("║", BOLD))
        lines.append(_c("╟" + "─" * (w - 2) + "╢", DIM))
        for i, f in enumerate(focus, 1):
            # Wrap long lines
            line = f"  {i}. {f}"
            if len(line) > w - 4:
                line = line[:w - 7] + "..."
            pad = w - 2 - len(line)
            lines.append(_c("║", DIM) + line + " " * max(pad, 0) + _c("║", DIM))
        lines.append(_c("╚" + "═" * (w - 2) + "╝", BOLD))

    lines.append("")
    return "\n".join(lines)
