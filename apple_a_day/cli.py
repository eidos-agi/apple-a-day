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
        print(json.dumps(output, indent=2))
        return

    render = _get_renderer()
    render(report, results, SEVERITY_ORDER, min_idx)


def _cmd_schema(_args):
    """Output JSON schema of all checks."""
    print(json.dumps(get_schema(), indent=2))


def main(argv=None):
    """apple-a-day: Mac health toolkit — keeps the doctor away."""
    parser = argparse.ArgumentParser(
        prog="aad",
        description="apple-a-day: Mac health toolkit — keeps the doctor away.",
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
