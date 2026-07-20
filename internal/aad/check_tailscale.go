package aad

import (
	"encoding/json"
	"fmt"
	"os"
)

// tailscaleBin: MAS build ships no CLI on PATH and crashes if symlinked (it
// reads its own invocation path for bundle identity), so call the bundled
// binary directly. Mirrors tailscale.py:_TS_BIN.
const tailscaleBin = "/Applications/Tailscale.app/Contents/MacOS/Tailscale"

// tailscaleStatus mirrors the subset of `tailscale status --json` fields the
// Python check reads.
type tailscaleStatus struct {
	BackendState string `json:"BackendState"`
	Self         struct {
		Online bool `json:"Online"`
	} `json:"Self"`
}

func init() {
	register(Check{Name: "Tailscale", Run: checkTailscale})
}

// checkTailscale flags Tailscale being down, needing login, or this node
// offline. Faithful port of tailscale.py:check_tailscale.
func checkTailscale() CheckResult {
	r := CheckResult{Name: "Tailscale"}

	// Python distinguishes FileNotFoundError (binary missing) from other
	// subprocess/JSON errors; run()/runT() collapse all failures to "", so
	// probe the bundled binary's existence first to preserve that split.
	if _, err := os.Stat(tailscaleBin); err != nil {
		r.add(Finding{
			Check:    "tailscale",
			Severity: INFO,
			Summary:  "Tailscale not installed",
		})
		return r
	}

	out := run(tailscaleBin, "status", "--json")
	var data tailscaleStatus
	if out == "" || json.Unmarshal([]byte(out), &data) != nil {
		r.add(Finding{
			Check:    "tailscale",
			Severity: WARNING,
			Summary:  "Could not read Tailscale status",
			Fix:      fmt.Sprintf("Run `%s status` manually.", tailscaleBin),
		})
		return r
	}

	state := data.BackendState
	if state == "" {
		state = "Unknown"
	}
	online := data.Self.Online

	switch {
	case state == "Running" && online:
		r.add(Finding{
			Check:    "tailscale",
			Severity: OK,
			Summary:  "Tailscale running, node online",
		})
	case state == "NeedsLogin":
		r.add(Finding{
			Check:    "tailscale",
			Severity: WARNING,
			Summary:  "Tailscale needs login",
			Details:  "Backend is up but not authenticated to the tailnet.",
			Fix:      fmt.Sprintf("Run `%s up` to reauthenticate.", tailscaleBin),
		})
	case state == "Stopped":
		r.add(Finding{
			Check:    "tailscale",
			Severity: WARNING,
			Summary:  "Tailscale is stopped",
			Fix:      fmt.Sprintf("Run `%s up` or start it from the menu bar.", tailscaleBin),
		})
	default:
		r.add(Finding{
			Check:    "tailscale",
			Severity: WARNING,
			Summary:  fmt.Sprintf("Tailscale state=%s, online=%t", state, online),
			Details:  "Backend is not in a healthy Running+online state.",
			Fix:      fmt.Sprintf("Check `%s status`; reconnect from the menu bar.", tailscaleBin),
		})
	}

	return r
}
