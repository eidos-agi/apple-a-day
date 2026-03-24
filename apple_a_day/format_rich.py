"""Optional Rich-based formatter. Only loaded when rich is installed."""

from rich.console import Console
from rich.table import Table

from .models import Severity

SEVERITY_COLORS = {
    Severity.OK: "green",
    Severity.INFO: "blue",
    Severity.WARNING: "yellow",
    Severity.CRITICAL: "red",
}


def render_report(report, results, severity_order, min_idx):
    """Render a CheckupReport using Rich tables."""
    console = Console()
    console.print()

    info = report.mac_info
    console.print("[bold]apple-a-day checkup[/bold]")
    mac_line = " | ".join(
        filter(
            None,
            [
                f"macOS {info.get('os_version', '?')}",
                info.get("cpu", ""),
                f"{info.get('memory_gb', '?')} GB RAM" if "memory_gb" in info else None,
            ],
        )
    )
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

    all_findings = [
        f for r in results for f in r.findings if severity_order.index(f.severity.value) >= min_idx
    ]
    crits = sum(1 for f in all_findings if f.severity == Severity.CRITICAL)
    warns = sum(1 for f in all_findings if f.severity == Severity.WARNING)

    parts = []
    if crits:
        parts.append(f"[red bold]{crits} critical[/red bold]")
    if warns:
        parts.append(f"[yellow]{warns} warning(s)[/yellow]")
    if not crits and not warns:
        parts.append("[green]All clear — your Mac is healthy.[/green]")

    console.print(" | ".join(parts) + f"  [dim]({report.duration_ms}ms)[/dim]")
