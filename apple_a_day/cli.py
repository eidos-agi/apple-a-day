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
        print(f"\n  Recurring issues:")
        for issue in trend["recurring"]:
            print(f"    \033[31m●\033[0m {issue}")


def _cmd_profile(args):
    """Show or refresh Mac user profile."""
    from .profile import get_or_create_profile

    profile = get_or_create_profile(force_refresh=args.refresh)

    if args.profile_json:
        print(json.dumps(profile, indent=2))
        return

    # Pretty print
    hw = profile.get("hardware", {})
    print(f"\napple-a-day user profile")
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
    print(f"  Stored: ~/.config/eidos/mac-profile.json")


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

    args = parser.parse_args(argv)

    if args.command is None:
        # Default to checkup
        args.command = "checkup"
        args.json = False
        args.no_parallel = False
        args.check = []
        args.min_severity = "ok"
        args.fields = None

    if args.command == "checkup":
        _cmd_checkup(args)
    elif args.command == "schema":
        _cmd_schema(args)
    elif args.command == "profile":
        _cmd_profile(args)
    elif args.command == "score":
        _cmd_score(args)
    elif args.command == "log":
        _cmd_log(args)
    elif args.command == "trend":
        _cmd_trend(args)
