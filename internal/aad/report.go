package aad

import (
	"encoding/json"
	"fmt"
	"strings"
)

// RenderText renders a checkup as human-readable text.
func RenderText(rep CheckupReport) string {
	var b strings.Builder
	worst := OK
	counts := map[Severity]int{}

	for _, r := range rep.Results {
		rs := r.WorstSeverity()
		if rs > worst {
			worst = rs
		}
		fmt.Fprintf(&b, "\n%s %s\n", rs.Icon(), r.Name)
		for _, e := range r.Errors {
			fmt.Fprintf(&b, "    ! %s: %s\n", e.ErrorCode, e.Message)
		}
		for _, f := range r.Findings {
			counts[f.Severity]++
			fmt.Fprintf(&b, "    %s %s\n", f.Severity.Icon(), f.Summary)
			for _, line := range strings.Split(f.Details, "\n") {
				if strings.TrimSpace(line) != "" {
					fmt.Fprintf(&b, "        %s\n", strings.TrimRight(line, " "))
				}
			}
			if f.Fix != "" {
				fmt.Fprintf(&b, "        → %s\n", f.Fix)
			}
		}
	}

	sc := ComputeScore(rep.Results)
	fmt.Fprintf(&b, "\n%s  overall: %s   score %d/100 (%s)   (%d critical, %d warning, %d info)  %dms\n",
		worst.Icon(), strings.ToUpper(worst.String()), sc.Score, sc.Grade,
		counts[CRITICAL], counts[WARNING], counts[INFO], rep.DurationMS)
	return b.String()
}

// RenderJSON renders a checkup as JSON (severities as strings).
func RenderJSON(rep CheckupReport) string {
	// Custom marshal so Severity emits its string, not its int.
	type jf struct {
		Check    string `json:"check"`
		Severity string `json:"severity"`
		Summary  string `json:"summary"`
		Details  string `json:"details,omitempty"`
		Fix      string `json:"fix,omitempty"`
	}
	type jr struct {
		Name     string       `json:"name"`
		Findings []jf         `json:"findings"`
		Errors   []CheckError `json:"errors,omitempty"`
	}
	var out struct {
		Results    []jr           `json:"results"`
		Score      Score          `json:"score"`
		DurationMS int64          `json:"duration_ms"`
		MacInfo    map[string]any `json:"mac_info"`
	}
	out.DurationMS = rep.DurationMS
	out.MacInfo = rep.MacInfo
	out.Score = ComputeScore(rep.Results)
	for _, r := range rep.Results {
		j := jr{Name: r.Name, Errors: r.Errors}
		for _, f := range r.Findings {
			j.Findings = append(j.Findings, jf{f.Check, f.Severity.String(), f.Summary, f.Details, f.Fix})
		}
		out.Results = append(out.Results, j)
	}
	buf, _ := json.MarshalIndent(out, "", "  ")
	return string(buf)
}
