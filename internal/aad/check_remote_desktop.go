package aad

import (
	"fmt"
	"strings"
	"time"
)

func init() {
	register(Check{Name: "Remote Desktop", Run: checkRemoteDesktop})
}

// remoteDesktopTools mirrors remote_desktop.py:_REMOTE_TOOLS. Order matters
// for a stable, deterministic "running" list (Python relies on dict
// insertion order).
var remoteDesktopTools = []string{
	"DeskIn",
	"Screen Sharing",
	"Microsoft Remote Desktop",
	"Windows App",
}

func checkRemoteDesktop() CheckResult {
	r := CheckResult{Name: "Remote Desktop"}

	// mirrors remote_desktop.py:20-25 — `ps -eo args`, 5s timeout.
	// ponytail: runT() collapses timeout/OSError to "" like the shared subprocess
	// idiom elsewhere in this package, so the specific exception message from
	// Python's `f"Could not inspect processes: {e}"` isn't reproducible here;
	// deferred — a generic summary preserves the verdict (INFO, no crash).
	out := runT(5*time.Second, "ps", "-eo", "args")
	if out == "" {
		r.add(Finding{
			Check:    "remote_desktop",
			Severity: INFO,
			Summary:  "Could not inspect processes",
		})
		return r
	}

	var running []string
	for _, label := range remoteDesktopTools {
		if strings.Contains(out, label) {
			running = append(running, label)
		}
	}

	switch {
	case len(running) >= 2:
		joined := strings.Join(running, ", ")
		r.add(Finding{
			Check:    "remote_desktop",
			Severity: WARNING,
			Summary:  fmt.Sprintf("%d remote desktop tools active: %s", len(running), joined),
			Details:  "Each remote path competes for WindowServer CPU and network bandwidth.",
			Fix:      fmt.Sprintf("Pick one remote tool — quit the other(s): %s.", joined),
		})
	case len(running) == 1:
		r.add(Finding{
			Check:    "remote_desktop",
			Severity: INFO,
			Summary:  fmt.Sprintf("Remote desktop active: %s", running[0]),
		})
	default:
		r.add(Finding{
			Check:    "remote_desktop",
			Severity: OK,
			Summary:  "No remote desktop clients detected",
		})
	}

	return r
}
