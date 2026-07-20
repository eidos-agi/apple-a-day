package aad

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"time"
)

// resource-sentinel is the sibling Go daemon: the always-on mutating enforcer
// (safe-cleans caches, truncates oversized logs, SIGSTOPs runaway writers).
// aad is read-only and never mutates; this check makes aad the single pane of
// glass over that enforcer by reading its localhost status API. Deliberately
// does NOT re-report free-GB severity — that stays check_disk's job. It reports
// the guardian's *state*: alive, what it paused, what it cleaned.
func init() {
	register(Check{Name: "Resource Sentinel", Run: checkResourceSentinel})
}

const sentinelStatusURL = "http://127.0.0.1:9341/status"
const sentinelRestart = "launchctl kickstart -k gui/$(id -u)/com.eidos.resource-sentinel"

type sentinelStatus struct {
	FreeGB       int      `json:"free_gb"`
	PausedPIDs   []string `json:"paused_pids"`
	RecentAlerts []string `json:"recent_alerts"`
}

// classifySentinel turns a status payload into one Finding. Pure — offline-testable.
func classifySentinel(s sentinelStatus) Finding {
	switch {
	case len(s.PausedPIDs) > 0:
		return Finding{
			Check: "resource_sentinel", Severity: WARNING,
			Summary: fmt.Sprintf("Guardian SIGSTOP'd %d process(es) — awaiting your call", len(s.PausedPIDs)),
			Details: "Paused (kill -STOP) writers: " + strings.Join(s.PausedPIDs, ", "),
			Fix:     "Resume with `kill -CONT <pid>` once you've dealt with the disk pressure. See `sentinel` CLI / :9341/logs.",
		}
	case len(s.RecentAlerts) > 0:
		return Finding{
			Check: "resource_sentinel", Severity: INFO,
			Summary: fmt.Sprintf("Guardian healthy, acted recently (%d GB free)", s.FreeGB),
			Details: "Latest: " + s.RecentAlerts[len(s.RecentAlerts)-1],
		}
	default:
		return Finding{
			Check: "resource_sentinel", Severity: OK,
			Summary: fmt.Sprintf("Guardian healthy, quiet (%d GB free)", s.FreeGB),
		}
	}
}

func checkResourceSentinel() CheckResult {
	r := CheckResult{Name: "Resource Sentinel"}
	client := http.Client{Timeout: 3 * time.Second}
	resp, err := client.Get(sentinelStatusURL)
	if err != nil {
		r.add(Finding{
			Check: "resource_sentinel", Severity: CRITICAL,
			Summary: "GUARDIAN DOWN — resource-sentinel not responding on :9341",
			Details: "The always-on disk/RAM/CPU guardian is unreachable. Nothing is safe-cleaning caches or naming runaway writers.",
			Fix:     "Restart it: `" + sentinelRestart + "` (binary at ~/.local/bin/resource-sentinel).",
		})
		return r
	}
	defer resp.Body.Close()

	var s sentinelStatus
	if err := json.NewDecoder(resp.Body).Decode(&s); err != nil {
		r.add(Finding{
			Check: "resource_sentinel", Severity: WARNING,
			Summary: "Guardian responded but status was unparseable",
			Details: err.Error(),
		})
		return r
	}
	r.add(classifySentinel(s))
	return r
}
