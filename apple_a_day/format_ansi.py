"""Zero-dependency ANSI terminal formatter using escape codes + Unicode box-drawing."""

import sys

# ANSI escape codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"

SEVERITY_STYLE = {
    "ok": GREEN,
    "info": BLUE,
    "warning": YELLOW,
    "critical": RED,
}


def _supports_color() -> bool:
    """Check if the terminal supports color output."""
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False
    return True


def _c(text: str, *codes: str) -> str:
    """Wrap text in ANSI codes if terminal supports color."""
    if not _supports_color():
        return text
    prefix = "".join(codes)
    return f"{prefix}{text}{RESET}"


def render_report(report, results, severity_order, min_idx):
    """Render a CheckupReport to the terminal using ANSI codes."""
    lines = []

    # Header
    info = report.mac_info
    lines.append("")
    lines.append(_c("apple-a-day checkup", BOLD))
    mac_parts = [f"macOS {info.get('os_version', '?')}"]
    if info.get("cpu"):
        mac_parts.append(info["cpu"])
    if "memory_gb" in info:
        mac_parts.append(f"{info['memory_gb']} GB RAM")
    lines.append(_c(" | ".join(mac_parts), DIM))
    lines.append("")

    # Each check result
    for r in results:
        filtered = [f for f in r.findings if severity_order.index(f.severity.value) >= min_idx]
        if not filtered:
            continue

        # Section header
        lines.append(_c(f"── {r.name} ", BOLD) + _c("─" * max(0, 60 - len(r.name)), DIM))

        for f in filtered:
            style = SEVERITY_STYLE[f.severity.value]
            icon = f.icon

            # Finding line
            lines.append(f"  {_c(icon, style)} {_c(f.summary, style)}")
            if f.details:
                lines.append(f"    {_c(f.details, DIM)}")
            if f.fix:
                # Wrap long fix lines
                fix_lines = f.fix.split("\n")
                for fl in fix_lines:
                    lines.append(f"    {_c('→', DIM)} {_c(fl, DIM)}")

        lines.append("")

    # Summary
    all_findings = [
        f for r in results for f in r.findings if severity_order.index(f.severity.value) >= min_idx
    ]
    crits = sum(1 for f in all_findings if f.severity.value == "critical")
    warns = sum(1 for f in all_findings if f.severity.value == "warning")

    parts = []
    if crits:
        parts.append(_c(f"{crits} critical", RED, BOLD))
    if warns:
        parts.append(_c(f"{warns} warning(s)", YELLOW))
    if not crits and not warns:
        parts.append(_c("All clear — your Mac is healthy.", GREEN))

    lines.append(" | ".join(parts) + "  " + _c(f"({report.duration_ms}ms)", DIM))

    print("\n".join(lines))
