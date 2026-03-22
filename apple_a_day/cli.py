"""CLI entry point: `aad` command."""

import click
from rich.console import Console
from rich.table import Table

from . import __version__
from .models import Severity
from .runner import run_all_checks


SEVERITY_COLORS = {
    Severity.OK: "green",
    Severity.INFO: "blue",
    Severity.WARNING: "yellow",
    Severity.CRITICAL: "red",
}


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="apple-a-day")
@click.pass_context
def main(ctx):
    """apple-a-day: Mac health toolkit — keeps the doctor away."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(checkup)


@main.command()
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.option("--no-parallel", is_flag=True, help="Run checks sequentially")
@click.option("--check", "-c", multiple=True, help="Run only specific check(s) by name")
@click.option("--min-severity", type=click.Choice(["ok", "info", "warning", "critical"]),
              default="ok", help="Only show findings at or above this severity")
def checkup(as_json: bool = False, no_parallel: bool = False, check: tuple = (),
            min_severity: str = "ok"):
    """Run all health checks."""
    report = run_all_checks(parallel=not no_parallel)

    severity_order = ["ok", "info", "warning", "critical"]
    min_idx = severity_order.index(min_severity)

    # Filter checks if specified
    results = report.results
    if check:
        check_lower = {c.lower() for c in check}
        results = [r for r in results if r.name.lower().replace(" ", "_") in check_lower
                   or r.name.lower() in check_lower]

    if as_json:
        import json
        output = {
            "mac": report.mac_info,
            "duration_ms": report.duration_ms,
            "findings": [],
        }
        for r in results:
            for f in r.findings:
                if severity_order.index(f.severity.value) >= min_idx:
                    output["findings"].append({
                        "check": r.name,
                        "severity": f.severity.value,
                        "summary": f.summary,
                        "details": f.details,
                        "fix": f.fix,
                    })
        click.echo(json.dumps(output, indent=2))
        return

    console = Console()
    console.print()

    # Header with Mac info
    info = report.mac_info
    header = f"[bold]apple-a-day checkup[/bold]"
    mac_line = " | ".join(filter(None, [
        f"macOS {info.get('os_version', '?')}",
        info.get("cpu", ""),
        f"{info.get('memory_gb', '?')} GB RAM" if "memory_gb" in info else None,
    ]))
    console.print(header)
    console.print(f"[dim]{mac_line}[/dim]")
    console.print()

    for r in results:
        filtered = [f for f in r.findings if severity_order.index(f.severity.value) >= min_idx]
        if not filtered:
            continue

        table = Table(title=r.name, show_header=False, border_style="dim", pad_edge=False)
        table.add_column("", width=2)
        table.add_column("Finding")
        table.add_column("Fix", style="dim")

        for f in filtered:
            color = SEVERITY_COLORS[f.severity]
            table.add_row(
                f"[{color}]{f.icon}[/{color}]",
                f"[{color}]{f.summary}[/{color}]" + (f"\n  {f.details}" if f.details else ""),
                f.fix if f.fix else "",
            )

        console.print(table)
        console.print()

    # Summary
    all_findings = [f for r in results for f in r.findings
                    if severity_order.index(f.severity.value) >= min_idx]
    crits = sum(1 for f in all_findings if f.severity == Severity.CRITICAL)
    warns = sum(1 for f in all_findings if f.severity == Severity.WARNING)

    summary_parts = []
    if crits:
        summary_parts.append(f"[red bold]{crits} critical[/red bold]")
    if warns:
        summary_parts.append(f"[yellow]{warns} warning(s)[/yellow]")
    if not crits and not warns:
        summary_parts.append("[green]All clear — your Mac is healthy.[/green]")

    console.print(" | ".join(summary_parts) + f"  [dim]({report.duration_ms}ms)[/dim]")
