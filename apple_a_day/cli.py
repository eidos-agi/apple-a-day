"""CLI entry point: `aad` command. Zero dependencies — stdlib argparse only."""

import argparse
import json

from . import __version__
from .runner import run_all_checks
from .schema import get_schema


SEVERITY_ORDER = ["ok", "info", "warning", "critical"]


def _get_renderer():
    """Auto-detect: use Rich if installed, fall back to ANSI."""
    try:
        from .format_rich import render_report
        return render_report
    except ImportError:
        from .format_ansi import render_report
        return render_report


def _cmd_checkup(args):
    """Run all health checks."""
    report = run_all_checks(parallel=not args.no_parallel)
    min_idx = SEVERITY_ORDER.index(args.min_severity)

    results = report.results
    if args.check:
        check_lower = {c.lower() for c in args.check}
        results = [r for r in results if r.name.lower().replace(" ", "_") in check_lower
                   or r.name.lower() in check_lower]

    if args.json:
        output = {
            "mac": report.mac_info,
            "duration_ms": report.duration_ms,
            "findings": [],
            "errors": [],
        }
        for r in results:
            for f in r.findings:
                if SEVERITY_ORDER.index(f.severity.value) >= min_idx:
                    finding = {
                        "check": r.name,
                        "severity": f.severity.value,
                        "summary": f.summary,
                        "details": f.details,
                        "fix": f.fix,
                    }
                    if args.fields:
                        finding = {k: v for k, v in finding.items() if k in args.fields}
                    output["findings"].append(finding)
            for e in r.errors:
                output["errors"].append(e.to_dict())
        if not output["errors"]:
            del output["errors"]
        print(json.dumps(output, indent=2))
        return

    render = _get_renderer()
    render(report, results, SEVERITY_ORDER, min_idx)


def _cmd_schema(_args):
    """Output JSON schema of all checks."""
    print(json.dumps(get_schema(), indent=2))


def _cmd_score(args):
    """Show health score matrix from latest checkup."""
    from .log import read_recent

    entries = read_recent(1)
    if not entries:
        print("No scores yet. Run `aad checkup` first.")
        return

    latest = entries[-1]

    if args.score_json:
        print(json.dumps({
            "ts": latest.get("ts"),
            "score": latest.get("score"),
            "grade": latest.get("grade"),
            "matrix": latest.get("matrix", {}),
        }, indent=2))
        return

    score = latest.get("score", 0)
    grade = latest.get("grade", "?")
    matrix = latest.get("matrix", {})
    ts = latest.get("ts", "?")[:19]

    # Color the grade
    grade_colors = {"A": "\033[32m", "B": "\033[32m", "C": "\033[33m", "D": "\033[31m", "F": "\033[31m"}
    gc = grade_colors.get(grade, "")

    print(f"\napple-a-day health score  {gc}{grade} ({score}/100)\033[0m  {ts}")
    print()

    # Matrix as visual bars
    dim_labels = {
        "stability": "Stability  ",
        "memory": "Memory     ",
        "storage": "Storage    ",
        "services": "Services   ",
        "security": "Security   ",
        "infra": "Infra      ",
        "network": "Network    ",
    }

    for dim, label in dim_labels.items():
        val = matrix.get(dim, 100)
        bar_len = val // 5  # 0-20 chars
        if val >= 80:
            color = "\033[32m"
        elif val >= 50:
            color = "\033[33m"
        else:
            color = "\033[31m"

        bar = "█" * bar_len + "░" * (20 - bar_len)
        print(f"  {label} {color}{bar}\033[0m {val}")

    print()

    # Criticals summary
    crits = latest.get("criticals", [])
    if crits:
        print(f"  \033[31m{len(crits)} critical issue(s):\033[0m")
        for c in crits[:5]:
            print(f"    ✗ {c[:70]}")


def _cmd_log(args):
    """Show recent checkup log entries."""
    from .log import read_recent

    entries = read_recent(args.n)
    if not entries:
        print("No log entries yet. Run `aad checkup` first.")
        return

    if args.log_json:
        print(json.dumps(entries, indent=2))
        return

    for e in entries:
        ts = e.get("ts", "?")[:19]
        c = e.get("counts", {})
        crits = c.get("critical", 0)
        warns = c.get("warning", 0)
        ms = e.get("duration_ms", 0)

        status = "\033[32mhealthy\033[0m"
        if crits > 0:
            status = f"\033[31m{crits} critical\033[0m"
        elif warns > 0:
            status = f"\033[33m{warns} warning\033[0m"

        print(f"  {ts}  {status}  ({ms}ms)")
        for crit in e.get("criticals", [])[:3]:
            print(f"    \033[31m✗\033[0m {crit[:70]}")


def _cmd_trend(args):
    """Show health trend from logs."""
    from .log import trend_summary

    trend = trend_summary()
    if not trend:
        print("Not enough log entries for trends. Run `aad checkup` a few times first.")
        return

    if args.trend_json:
        print(json.dumps(trend, indent=2))
        return

    direction = "\033[32m↑ improving\033[0m" if trend["improving"] else "\033[31m↓ degrading\033[0m"
    print(f"\napple-a-day health trend ({trend['entries']} checkups, {trend['first']} → {trend['last']})")
    print(f"  Direction: {direction}")
    print(f"  Avg criticals: {trend['avg_criticals']}  |  Avg warnings: {trend['avg_warnings']}")

    if trend["recurring"]:
        print("\n  Recurring issues:")
        for issue in trend["recurring"]:
            print(f"    \033[31m●\033[0m {issue}")


def _cmd_report(args):
    """Generate a focused health report."""
    if args.html:
        from .report_html import open_report
        path = open_report(vitals_minutes=args.minutes)
        print(f"Report opened: {path}")
        return

    if args.report_json:
        from .report import generate_report
        result = generate_report(as_json=True, vitals_minutes=args.minutes)
        print(json.dumps(result, indent=2))
        return

    from .report import generate_report
    print(generate_report(as_json=False, vitals_minutes=args.minutes))


def _cmd_monitor(args):
    """Run vitals monitor — single sample or continuous loop."""
    from .vitals import run_monitor

    if args.once:
        s = run_monitor(once=True)
        if args.monitor_json:
            print(json.dumps(s, indent=2))
        else:
            load = s.get("load", [0, 0, 0])
            top = s.get("top", [])
            print(f"Sampled: load {load[0]:.1f}/{load[1]:.1f}/{load[2]:.1f}"
                  f"  thermal={s.get('thermal', '?')}"
                  f"  swap={s.get('swap_mb', '?')}MB")
            if top:
                for cpu, name in top[:3]:
                    print(f"  {name}: {cpu}%")
        return

    # Continuous mode
    print(f"Monitoring every {args.interval}s (Ctrl-C to stop)...")
    run_monitor(interval=args.interval)


def _cmd_vitals(args):
    """Analyze vitals history — show spikes, trends, offenders."""
    from .vitals import analyze_vitals

    analysis = analyze_vitals(minutes=args.minutes)

    if not analysis.get("samples"):
        print("No vitals data yet. Run `aad monitor --once` or start the monitor.")
        return

    if args.vitals_json:
        print(json.dumps(analysis, indent=2))
        return

    load = analysis.get("load", {})
    thermal = analysis.get("thermal", {})
    swap = analysis.get("swap", {})
    spikes = load.get("spikes", [])
    offenders = analysis.get("worst_offenders", [])

    print(f"\napple-a-day vitals ({analysis['samples']} samples, last {args.minutes}min)")
    print(f"\n  Load: current {_fmt_load(load.get('current', []))}  "
          f"peak {load.get('peak_1m', 0):.0f}  avg {load.get('avg_1m', 0):.1f}  "
          f"({load.get('cores', '?')} cores)")

    if spikes:
        print(f"\n  \033[31m{len(spikes)} load spike(s) detected:\033[0m")
        for s in spikes[:5]:
            ongoing = " \033[31m(ONGOING)\033[0m" if s.get("ongoing") else ""
            procs = ", ".join(f"{p[1]} ({p[0]}%)" for p in s.get("top_processes", []))
            print(f"    peak {s['peak_load']:.0f}x  {s['start'][:19]}{ongoing}")
            if procs:
                print(f"      culprits: {procs}")

    t_level = {0: "nominal", 1: "moderate", 2: "heavy", 3: "trapping", 4: "sleeping"}
    print(f"\n  Thermal: current {t_level.get(thermal.get('current', 0), '?')}  "
          f"peak {t_level.get(thermal.get('peak', 0), '?')}  "
          f"above-nominal {thermal.get('time_above_nominal_pct', 0):.0f}% of time")

    print(f"\n  Swap: current {swap.get('current_mb', '?')}MB  peak {swap.get('peak_mb', 0):.0f}MB")

    if offenders:
        print("\n  Top offenders (by frequency in top-CPU list):")
        for o in offenders[:7]:
            print(f"    {o['name']:30s}  seen {o['appearances']}x  peak {o['peak_cpu']}%")

    print()


def _fmt_load(load_list):
    if not load_list:
        return "?"
    return "/".join(f"{v:.0f}" for v in load_list[:3])


def _cmd_install(_args):
    """Install the vitals monitor daemon."""
    from .launchd import install
    print(install())


def _cmd_uninstall(_args):
    """Remove the vitals monitor daemon."""
    from .launchd import uninstall
    print(uninstall())


def _cmd_status(_args):
    """Check daemon status."""
    from .launchd import status
    print(status())


def _cmd_profile(args):
    """Show or refresh Mac user profile."""
    from .profile import get_or_create_profile

    profile = get_or_create_profile(force_refresh=args.refresh)

    if args.profile_json:
        print(json.dumps(profile, indent=2))
        return

    # Pretty print
    hw = profile.get("hardware", {})
    print("\napple-a-day user profile")
    print(f"  {hw.get('cpu', '?')} | {hw.get('memory_gb', '?')} GB RAM"
          f" | {hw.get('disk_gb', '?')} GB disk | macOS {hw.get('os_version', '?')}")
    print(f"\n  User type: {profile.get('user_type', 'unknown')}")
    print(f"  Tags: {', '.join(profile.get('tags', []))}")

    tools = profile.get("dev_tools", {})
    if tools:
        print(f"\n  Dev tools ({len(tools)}):")
        for name, ver in sorted(tools.items()):
            print(f"    {name}: {ver[:60]}")

    editors = profile.get("editors", [])
    if editors:
        print(f"\n  Editors: {', '.join(editors)}")

    ws = profile.get("workspace", {})
    if ws.get("repo_count"):
        print(f"\n  Repos: {ws['repo_count']} across {len(ws.get('repo_dirs', []))} directories")
        langs = ws.get("languages", {})
        if langs:
            print(f"  Languages: {', '.join(f'{k} ({v})' for k, v in langs.items())}")

    top = profile.get("top_commands", [])[:10]
    if top:
        print(f"\n  Top commands: {', '.join(c['command'] for c in top)}")

    print(f"\n  Profiled: {profile.get('gathered_at', '?')[:19]}")
    print("  Stored: ~/.config/eidos/mac-profile.json")


def main(argv=None):
    """apple-a-day: Mac health toolkit — keeps the doctor away."""
    parser = argparse.ArgumentParser(
        prog="aad",
        description="aad (apple-a-day): Mac health toolkit — keeps the doctor away. https://github.com/eidos-agi/apple-a-day",
    )
    parser.add_argument("--version", action="version", version=f"apple-a-day {__version__}")

    sub = parser.add_subparsers(dest="command")

    # checkup
    p_checkup = sub.add_parser("checkup", help="Run all health checks")
    p_checkup.add_argument("--json", action="store_true", help="Output as JSON")
    p_checkup.add_argument("--no-parallel", action="store_true", help="Run checks sequentially")
    p_checkup.add_argument("-c", "--check", action="append", default=[],
                           help="Run only specific check(s) by name (repeatable)")
    p_checkup.add_argument("--min-severity", choices=SEVERITY_ORDER, default="ok",
                           help="Only show findings at or above this severity")
    p_checkup.add_argument("--fields", type=lambda s: set(s.split(",")),
                           help="Comma-separated fields to include in JSON output")

    # schema
    sub.add_parser("schema", help="Show JSON schema of all checks and output format")

    # profile
    p_profile = sub.add_parser("profile", help="Show or refresh Mac user profile")
    p_profile.add_argument("--refresh", action="store_true", help="Force re-gather profile data")
    p_profile.add_argument("--json", action="store_true", dest="profile_json", help="Output as JSON")

    # score
    p_score = sub.add_parser("score", help="Show health score matrix from latest checkup")
    p_score.add_argument("--json", action="store_true", dest="score_json", help="Output as JSON")

    # log
    p_log = sub.add_parser("log", help="Show recent checkup log entries")
    p_log.add_argument("-n", type=int, default=5, help="Number of entries (default: 5)")
    p_log.add_argument("--json", action="store_true", dest="log_json", help="Output as JSON")

    # trend
    p_trend = sub.add_parser("trend", help="Show health trend from logs")
    p_trend.add_argument("--json", action="store_true", dest="trend_json", help="Output as JSON")

    # report
    p_report = sub.add_parser("report", help="Focused health report with ASCII graphs")
    p_report.add_argument("--json", action="store_true", dest="report_json", help="Output as JSON")
    p_report.add_argument("--html", action="store_true", help="Open report in browser")
    p_report.add_argument("--minutes", type=int, default=60, help="Vitals lookback in minutes (default: 60)")

    # monitor
    p_monitor = sub.add_parser("monitor", help="Sample system vitals over time")
    p_monitor.add_argument("--once", action="store_true", help="Take a single sample and exit")
    p_monitor.add_argument("--interval", type=int, default=60, help="Seconds between samples (default: 60)")
    p_monitor.add_argument("--json", action="store_true", dest="monitor_json", help="Output as JSON")

    # vitals
    p_vitals = sub.add_parser("vitals", help="Analyze recent vitals history")
    p_vitals.add_argument("--minutes", type=int, default=60, help="Look back N minutes (default: 60)")
    p_vitals.add_argument("--json", action="store_true", dest="vitals_json", help="Output as JSON")

    # install / uninstall / status (daemon management)
    sub.add_parser("install", help="Install vitals monitor as a launchd daemon (samples every 60s)")
    sub.add_parser("uninstall", help="Remove the vitals monitor daemon")
    sub.add_parser("status", help="Check vitals monitor daemon status")

    args = parser.parse_args(argv)

    if args.command is None:
        # Default to checkup
        args.command = "checkup"
        args.json = False
        args.no_parallel = False
        args.check = []
        args.min_severity = "ok"
        args.fields = None

    handlers = {
        "checkup": _cmd_checkup,
        "report": _cmd_report,
        "schema": _cmd_schema,
        "profile": _cmd_profile,
        "score": _cmd_score,
        "log": _cmd_log,
        "trend": _cmd_trend,
        "monitor": _cmd_monitor,
        "vitals": _cmd_vitals,
        "install": _cmd_install,
        "uninstall": _cmd_uninstall,
        "status": _cmd_status,
    }
    handlers[args.command](args)
