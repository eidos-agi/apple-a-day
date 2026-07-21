"""Check Tailscale is installed, running, and this node is online."""

import json
import subprocess

from ..models import CheckResult, Finding, Severity

# ponytail: MAS build ships no CLI on PATH and crashes if symlinked (it reads
# its own invocation path for bundle identity), so call the bundled binary directly.
_TS_BIN = "/Applications/Tailscale.app/Contents/MacOS/Tailscale"


def check_tailscale() -> CheckResult:
    """Flag Tailscale being down, needing login, or this node offline."""
    result = CheckResult(name="Tailscale")

    try:
        out = subprocess.run(
            [_TS_BIN, "status", "--json"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        data = json.loads(out.stdout)
    except FileNotFoundError:
        result.findings.append(
            Finding(
                check="tailscale",
                severity=Severity.INFO,
                summary="Tailscale not installed",
            )
        )
        return result
    except (subprocess.TimeoutExpired, OSError, json.JSONDecodeError) as e:
        result.findings.append(
            Finding(
                check="tailscale",
                severity=Severity.WARNING,
                summary=f"Could not read Tailscale status: {e}",
                fix=f"Run `{_TS_BIN} status` manually.",
            )
        )
        return result

    state = data.get("BackendState", "Unknown")
    online = data.get("Self", {}).get("Online", False)

    if state == "Running" and online:
        result.findings.append(
            Finding(
                check="tailscale",
                severity=Severity.OK,
                summary="Tailscale running, node online",
            )
        )
    elif state == "NeedsLogin":
        result.findings.append(
            Finding(
                check="tailscale",
                severity=Severity.WARNING,
                summary="Tailscale needs login",
                details="Backend is up but not authenticated to the tailnet.",
                fix=f"Run `{_TS_BIN} up` to reauthenticate.",
            )
        )
    elif state == "Stopped":
        result.findings.append(
            Finding(
                check="tailscale",
                severity=Severity.WARNING,
                summary="Tailscale is stopped",
                fix=f"Run `{_TS_BIN} up` or start it from the menu bar.",
            )
        )
    else:
        result.findings.append(
            Finding(
                check="tailscale",
                severity=Severity.WARNING,
                summary=f"Tailscale state={state}, online={online}",
                details="Backend is not in a healthy Running+online state.",
                fix=f"Check `{_TS_BIN} status`; reconnect from the menu bar.",
            )
        )

    return result
