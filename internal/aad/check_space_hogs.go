package aad

import (
	"encoding/json"
	"fmt"
	"sort"
	"strings"
	"time"
)

// Space Hogs folds the space-hog tool (github.com/eidos-agi/space-hog) into aad
// as a plugin (space-hog's TASK-0024). aad is read-only: space-hog does the
// scanning via `space-hog --json`, aad translates its sections into findings.
// Opt-in — the scan walks caches/downloads/home and takes minutes:
// `aad checkup -c "Space Hogs"`.
func init() {
	register(Check{Name: "Space Hogs", Run: checkSpaceHogs, OptIn: true})
}

type spaceHogItem struct {
	Bytes int64  `json:"bytes"`
	Label string `json:"label"`
	Path  string `json:"path"`
}
type spaceHogSection struct {
	Name       string         `json:"name"`
	TotalBytes int64          `json:"total_bytes"`
	Items      []spaceHogItem `json:"items"`
}
type spaceHogReport struct {
	TotalReclaimableBytes int64             `json:"total_reclaimable_bytes"`
	Sections              []spaceHogSection `json:"sections"`
}

func gb(bytes int64) float64 { return float64(bytes) / 1e9 }

// spaceHogFindings translates a space-hog report into findings. Pure — testable
// without running the scan. Finder stays INFO; check_disk owns the disk verdict.
func spaceHogFindings(rep spaceHogReport) []Finding {
	out := []Finding{{
		Check:    "space_hogs",
		Severity: INFO,
		Summary:  fmt.Sprintf("space-hog: %.1f GB reclaimable across %d areas", gb(rep.TotalReclaimableBytes), countNonEmpty(rep.Sections)),
		Fix:      "Read-only — aad finds, you decide. Rebuildable caches/Docker → delete locally; work docs → M-Files; never rm data you can't recreate. Run `space-hog --advise` for guided cleanup.",
	}}

	secs := append([]spaceHogSection(nil), rep.Sections...)
	sort.SliceStable(secs, func(i, j int) bool { return secs[i].TotalBytes > secs[j].TotalBytes })
	for _, s := range secs {
		if s.TotalBytes <= 0 {
			continue
		}
		var b strings.Builder
		items := s.Items
		if len(items) > 8 {
			items = items[:8]
		}
		for _, it := range items {
			fmt.Fprintf(&b, "  %6.1f GB  %s\n", gb(it.Bytes), it.Label)
		}
		out = append(out, Finding{
			Check:    "space_hogs",
			Severity: INFO,
			Summary:  fmt.Sprintf("%s: %.1f GB (%d items)", s.Name, gb(s.TotalBytes), len(s.Items)),
			Details:  strings.TrimRight(b.String(), "\n"),
		})
	}
	return out
}

func countNonEmpty(secs []spaceHogSection) int {
	n := 0
	for _, s := range secs {
		if s.TotalBytes > 0 {
			n++
		}
	}
	return n
}

func checkSpaceHogs() CheckResult {
	r := CheckResult{Name: "Space Hogs"}
	if run("which", "space-hog") == "" {
		r.add(Finding{
			Check: "space_hogs", Severity: INFO,
			Summary: "space-hog not installed — plugin unavailable",
			Fix:     "Install it: `pipx install space-hog` (repo: eidos-agi/space-hog).",
		})
		return r
	}
	// 90s cap (was 4m): space-hog's deep scan hangs for minutes on a
	// pressured disk, and agents running checkup as preflight would block.
	out := runT(90*time.Second, "space-hog", "--json")
	if out == "" {
		r.add(Finding{
			Check: "space_hogs", Severity: INFO,
			Summary: "space-hog scan timed out (90s cap) — skipped",
			Fix:     "Use `aad reclaim-plan --json` for fast ranked reclaim candidates; run space-hog manually when the machine is idle.",
		})
		return r
	}
	var rep spaceHogReport
	if err := json.Unmarshal([]byte(out), &rep); err != nil {
		r.Errors = append(r.Errors, CheckError{
			Check: "space_hogs", ErrorCode: "PARSE_ERROR", Message: err.Error(),
		})
		return r
	}
	r.Findings = spaceHogFindings(rep)
	return r
}
