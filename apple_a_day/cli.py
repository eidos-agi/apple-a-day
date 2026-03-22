"""CLI entry point: `aad` command."""

import click
from rich.console import Console
from rich.table import Table

from .models import Severity
from .runner import run_all_checks


SEVERITY_COLORS = {
    Severity.OK: "green",
    Severity.INFO: "blue",
    Severity.WARNING: "yellow",
    Severity.CRITICAL: "red",
}


@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx):
    """apple-a-day: Mac health toolkit — keeps the doctor away."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(checkup)


@main.command()
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def checkup(as_json: bool = False):
    """Run all health checks."""
    results = run_all_checks()

    if as_json:
        import json
        output = []
        for r in results:
            for f in r.findings:
                output.append({
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
    console.print("[bold]apple-a-day checkup[/bold]", style="bold")
    console.print()

    for r in results:
        table = Table(title=r.name, show_header=False, border_style="dim", pad_edge=False)
        table.add_column("", width=2)
        table.add_column("Finding")
        table.add_column("Fix", style="dim")

        for f in r.findings:
            color = SEVERITY_COLORS[f.severity]
            table.add_row(
                f"[{color}]{f.icon}[/{color}]",
                f"[{color}]{f.summary}[/{color}]" + (f"\n  {f.details}" if f.details else ""),
                f.fix if f.fix else "",
            )

        console.print(table)
        console.print()

    # Summary
    all_findings = [f for r in results for f in r.findings]
    crits = sum(1 for f in all_findings if f.severity == Severity.CRITICAL)
    warns = sum(1 for f in all_findings if f.severity == Severity.WARNING)

    if crits:
        console.print(f"[red bold]{crits} critical issue(s)[/red bold], {warns} warning(s)")
    elif warns:
        console.print(f"[yellow]{warns} warning(s)[/yellow], no critical issues")
    else:
        console.print("[green]All clear — your Mac is healthy.[/green]")
