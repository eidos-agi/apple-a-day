"""Render apple-a-day health report as a self-contained HTML file."""

import os
import webbrowser
from datetime import datetime
from pathlib import Path

from .log import read_recent
from .runner import run_all_checks
from .vitals import analyze_vitals, read_vitals


def _bar_svg(value: int, max_val: int = 100, width: int = 200, height: int = 18) -> str:
    """SVG horizontal bar."""
    filled = int(value / max_val * width)
    color = "#22c55e" if value >= 80 else "#eab308" if value >= 50 else "#ef4444"
    bg = "#1e293b"
    return (f'<svg width="{width}" height="{height}">'
            f'<rect width="{width}" height="{height}" rx="3" fill="{bg}"/>'
            f'<rect width="{filled}" height="{height}" rx="3" fill="{color}"/>'
            f'</svg>')


def _sparkline_svg(values: list[float], width: int = 500, height: int = 60) -> str:
    """SVG sparkline chart."""
    if not values:
        return ""
    mn, mx = min(values), max(values)
    rng = mx - mn if mx != mn else 1

    # Downsample
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
    # Area fill
    area = f"0,{height} " + polyline + f" {width},{height}"

    return (f'<svg width="{width}" height="{height}" style="display:block">'
            f'<polygon points="{area}" fill="rgba(56,189,248,0.15)"/>'
            f'<polyline points="{polyline}" fill="none" stroke="#38bdf8" stroke-width="1.5"/>'
            f'</svg>')


def _offender_bar(appearances: int, max_app: int, peak_cpu: float) -> str:
    """Inline bar for offender ranking."""
    w = int(appearances / max(max_app, 1) * 150)
    color = "#ef4444" if peak_cpu > 80 else "#eab308" if peak_cpu > 30 else "#38bdf8"
    return (f'<div style="display:inline-block;width:{w}px;height:14px;'
            f'background:{color};border-radius:2px;vertical-align:middle"></div>'
            f' <span style="color:#94a3b8;font-size:12px">{appearances}x · peak {peak_cpu}%</span>')


def _sev_badge(severity: str) -> str:
    """Severity badge."""
    colors = {
        "critical": ("bg:#ef4444", "#fff"),
        "warning": ("bg:#eab308", "#000"),
        "info": ("bg:#3b82f6", "#fff"),
        "ok": ("bg:#22c55e", "#fff"),
    }
    bg, fg = colors.get(severity, ("bg:#64748b", "#fff"))
    return (f'<span style="background:{bg.replace("bg:", "")};color:{fg};'
            f'padding:1px 8px;border-radius:3px;font-size:11px;font-weight:600;'
            f'text-transform:uppercase">{severity}</span>')


def generate_html_report(vitals_minutes: int = 60) -> str:
    """Run all checks and produce a self-contained HTML report."""
    report = run_all_checks(parallel=True)
    vitals = analyze_vitals(minutes=vitals_minutes)
    history = read_recent(10)
    samples = read_vitals(minutes=vitals_minutes)
    cores = os.cpu_count() or 8
    info = report.mac_info

    # Collect findings
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

    # Score matrix
    matrix = _compute_matrix(report)
    overall = matrix.pop("_overall", 0)
    grade = matrix.pop("_grade", "?")

    # Load data
    load_data = vitals.get("load", {})
    spikes = load_data.get("spikes", [])
    offenders = vitals.get("worst_offenders", [])

    # Trend
    trend = None
    if len(history) >= 3:
        recent = sum(e.get("counts", {}).get("critical", 0) for e in history[-3:]) / 3
        older = sum(e.get("counts", {}).get("critical", 0) for e in history[:3]) / 3
        trend = "improving" if recent < older else "degrading" if recent > older else "stable"

    # Focus items
    focus = _pick_focus(criticals, warnings, spikes, offenders)

    # Build HTML
    grade_color = {"A": "#22c55e", "B": "#22c55e", "C": "#eab308", "D": "#ef4444", "F": "#ef4444"}.get(grade, "#94a3b8")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>apple-a-day health report — {grade} ({overall}/100)</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'SF Mono', 'Fira Code', 'JetBrains Mono', monospace; padding: 24px; max-width: 860px; margin: 0 auto; }}
  h1 {{ font-size: 20px; font-weight: 700; margin-bottom: 4px; }}
  h2 {{ font-size: 15px; font-weight: 600; color: #94a3b8; margin: 28px 0 12px; border-bottom: 1px solid #1e293b; padding-bottom: 6px; }}
  .header {{ background: #1e293b; border-radius: 8px; padding: 20px 24px; margin-bottom: 24px; display: flex; justify-content: space-between; align-items: center; }}
  .header-left h1 {{ color: #f8fafc; }}
  .header-left .subtitle {{ color: #64748b; font-size: 13px; margin-top: 4px; }}
  .grade {{ font-size: 36px; font-weight: 800; color: {grade_color}; }}
  .grade-sub {{ font-size: 13px; color: #64748b; text-align: right; }}
  .matrix-row {{ display: flex; align-items: center; margin: 6px 0; }}
  .matrix-label {{ width: 90px; font-size: 13px; color: #94a3b8; }}
  .matrix-val {{ font-size: 13px; color: #64748b; margin-left: 8px; width: 30px; text-align: right; }}
  .card {{ background: #1e293b; border-radius: 8px; padding: 16px 20px; margin: 12px 0; }}
  .finding {{ padding: 8px 0; border-bottom: 1px solid #0f172a; }}
  .finding:last-child {{ border-bottom: none; }}
  .finding-summary {{ font-size: 13px; }}
  .finding-fix {{ font-size: 12px; color: #64748b; margin-top: 4px; }}
  .finding-fix code {{ background: #0f172a; padding: 2px 6px; border-radius: 3px; font-size: 11px; }}
  .offender {{ display: flex; align-items: center; margin: 6px 0; font-size: 13px; }}
  .offender-name {{ width: 200px; color: #e2e8f0; }}
  .focus-box {{ background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 1px solid #334155; border-radius: 8px; padding: 20px; margin: 24px 0; }}
  .focus-box h2 {{ border-bottom: none; margin: 0 0 12px; color: #f8fafc; font-size: 16px; }}
  .focus-item {{ padding: 6px 0; font-size: 13px; }}
  .focus-item .tag {{ font-weight: 700; }}
  .focus-item .tag-fix {{ color: #ef4444; }}
  .focus-item .tag-now {{ color: #f59e0b; }}
  .focus-item .tag-review {{ color: #eab308; }}
  .focus-item .tag-watch {{ color: #38bdf8; }}
  .spike {{ background: #1c1917; border-left: 3px solid #ef4444; padding: 8px 12px; margin: 6px 0; font-size: 12px; border-radius: 0 4px 4px 0; }}
  .spark-container {{ background: #1e293b; border-radius: 8px; padding: 16px 20px; }}
  .spark-stats {{ display: flex; gap: 24px; margin-top: 8px; font-size: 12px; color: #64748b; }}
  .spark-stat b {{ color: #e2e8f0; }}
  .trend {{ font-size: 14px; }}
  .trend-up {{ color: #22c55e; }}
  .trend-down {{ color: #ef4444; }}
  .trend-flat {{ color: #64748b; }}
  footer {{ margin-top: 32px; padding-top: 16px; border-top: 1px solid #1e293b; font-size: 11px; color: #475569; text-align: center; }}
</style>
</head>
<body>

<div class="header">
  <div class="header-left">
    <h1>apple-a-day health report</h1>
    <div class="subtitle">macOS {info.get('os_version', '?')} · {info.get('cpu', '?')} · {info.get('memory_gb', '?')} GB RAM · {now_str}</div>
  </div>
  <div style="text-align:right">
    <div class="grade">{grade}</div>
    <div class="grade-sub">{overall}/100</div>
  </div>
</div>
"""

    # ── Focus box (top) ──
    if focus:
        html += '<div class="focus-box"><h2>Focus</h2>\n'
        for i, f in enumerate(focus, 1):
            tag = f.split(":")[0] if ":" in f else "ACTION"
            rest = f.split(":", 1)[1].strip() if ":" in f else f
            tag_class = f"tag-{tag.lower()}"
            html += f'<div class="focus-item">{i}. <span class="tag {tag_class}">{tag}</span> {_esc(rest)}</div>\n'
        html += '</div>\n'

    # ── Health Matrix ──
    html += '<h2>Health Matrix</h2>\n'
    dim_labels = {
        "stability": "Stability", "cpu": "CPU", "thermal": "Thermal",
        "memory": "Memory", "storage": "Storage", "services": "Services",
        "security": "Security", "infra": "Infra", "network": "Network",
    }
    for dim, label in dim_labels.items():
        val = matrix.get(dim, 100)
        html += f'<div class="matrix-row"><span class="matrix-label">{label}</span>{_bar_svg(val)}<span class="matrix-val">{val}</span></div>\n'

    # ── Load Sparkline ──
    if samples:
        load_values = [s["load"][0] for s in samples if "load" in s]
        if load_values:
            peak = max(load_values)
            avg = sum(load_values) / len(load_values)
            html += '<h2>Load History</h2>\n'
            html += '<div class="spark-container">\n'
            html += _sparkline_svg(load_values, width=780, height=70)
            html += f'<div class="spark-stats"><span>peak: <b>{peak:.0f}</b></span><span>avg: <b>{avg:.1f}</b></span><span>cores: <b>{cores}</b></span><span>samples: <b>{len(load_values)}</b></span></div>\n'
            html += '</div>\n'

            if spikes:
                for s in spikes[:3]:
                    ongoing = ' <span style="color:#ef4444;font-weight:700">ONGOING</span>' if s.get("ongoing") else ""
                    procs = ", ".join(f"{p[1]} ({p[0]}%)" for p in s.get("top_processes", [])[:3])
                    html += f'<div class="spike">▲ spike peak <b>{s["peak_load"]:.0f}x</b> — {_esc(procs)}{ongoing}</div>\n'

    # ── Top Offenders ──
    if offenders:
        max_app = max(o["appearances"] for o in offenders[:7])
        html += '<h2>Top Resource Offenders</h2>\n<div class="card">\n'
        for o in offenders[:7]:
            html += f'<div class="offender"><span class="offender-name">{_esc(o["name"])}</span>{_offender_bar(o["appearances"], max_app, o["peak_cpu"])}</div>\n'
        html += '</div>\n'

    # ── Critical Issues ──
    if criticals:
        html += f'<h2 style="color:#ef4444">Critical Issues ({len(criticals)})</h2>\n<div class="card">\n'
        by_check: dict[str, list] = {}
        for c in criticals:
            by_check.setdefault(c["check"], []).append(c)
        for check, items in sorted(by_check.items(), key=lambda x: -len(x[1])):
            html += f'<div class="finding">{_sev_badge("critical")} <b>{_esc(check)}</b> — {len(items)} issue(s)\n'
            for item in items[:4]:
                html += f'<div style="margin-left:16px;font-size:12px;color:#cbd5e1;margin-top:2px">{_esc(item["summary"][:80])}</div>\n'
            if len(items) > 4:
                html += f'<div style="margin-left:16px;font-size:11px;color:#64748b">...and {len(items) - 4} more</div>\n'
            if items[0].get("fix"):
                html += f'<div class="finding-fix">→ {_esc(items[0]["fix"][:100])}</div>\n'
            html += '</div>\n'
        html += '</div>\n'

    # ── Warnings ──
    if warnings:
        html += f'<h2 style="color:#eab308">Warnings ({len(warnings)})</h2>\n<div class="card">\n'
        for w_item in warnings[:8]:
            html += f'<div class="finding">{_sev_badge("warning")} {_esc(w_item["summary"][:80])}\n'
            if w_item.get("fix"):
                html += f'<div class="finding-fix">→ {_esc(w_item["fix"][:100])}</div>\n'
            html += '</div>\n'
        if len(warnings) > 8:
            html += f'<div style="color:#64748b;font-size:12px;padding:8px 0">...and {len(warnings) - 8} more</div>\n'
        html += '</div>\n'

    # ── Info items (collapsed) ──
    if infos:
        html += f'<h2>Info ({len(infos)})</h2>\n<div class="card">\n'
        for item in infos[:6]:
            html += f'<div class="finding" style="color:#94a3b8">{_sev_badge("info")} {_esc(item["summary"][:80])}</div>\n'
        if len(infos) > 6:
            html += f'<div style="color:#64748b;font-size:12px;padding:8px 0">...and {len(infos) - 6} more</div>\n'
        html += '</div>\n'

    # ── Trend ──
    if trend:
        arrow = {"improving": ("↑ improving", "trend-up"), "degrading": ("↓ degrading", "trend-down"),
                 "stable": ("→ stable", "trend-flat")}.get(trend, ("?", ""))
        html += f'<h2>Trend</h2>\n<div class="card trend"><span class="{arrow[1]}" style="font-size:16px">{arrow[0]}</span></div>\n'

    html += f"""
<footer>
  apple-a-day v0.2.0 · generated {now_str} · {report.duration_ms}ms
</footer>
</body>
</html>"""

    return html


def open_report(vitals_minutes: int = 60) -> Path:
    """Generate HTML report, write to file, open in browser."""
    html = generate_html_report(vitals_minutes=vitals_minutes)
    report_dir = Path.home() / ".config" / "eidos" / "aad-logs"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "report.html"
    report_path.write_text(html)
    webbrowser.open(f"file://{report_path}")
    return report_path


def _esc(text: str) -> str:
    """Escape HTML entities."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _compute_matrix(report) -> dict:
    """Compute health score matrix."""
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

    grade = "A" if overall >= 90 else "B" if overall >= 75 else "C" if overall >= 50 else "D" if overall >= 25 else "F"
    matrix["_overall"] = overall
    matrix["_grade"] = grade
    return matrix


def _pick_focus(criticals, warnings, spikes, offenders) -> list[str]:
    """Top 3 things to focus on."""
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
