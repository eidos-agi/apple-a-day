package aad

// Health score matrix — verbatim port of Python compute_score_matrix so Go and
// the Python oracle produce identical scores during the transition.
// ponytail: "Resource Sentinel" and "Tailscale" aren't in any dimension here —
// that matches Python today (both are surfaced but unscored). Add to both maps
// together if they should count toward the score.

var dimensionChecks = map[string][]string{
	"stability": {"Crash Loops", "Kernel Panics", "Shutdown Causes"},
	"cpu":       {"CPU Load", "Agent Sprawl"},
	"thermal":   {"Thermal"},
	"memory":    {"Memory Pressure"},
	"storage":   {"Disk Health", "Docker Volumes"},
	"services":  {"Launch Agents", "Remote Desktop"},
	"security":  {"Security"},
	"infra":     {"Dynamic Library Health", "Homebrew"},
	"network":   {"Network"},
}

var dimensionWeights = map[string]int{
	"stability": 3, "cpu": 3, "memory": 2, "thermal": 2, "storage": 2,
	"services": 2, "security": 1, "infra": 1, "network": 1,
}

// Score is the computed health score.
type Score struct {
	Matrix map[string]int `json:"matrix"`
	Score  int            `json:"score"`
	Grade  string         `json:"grade"`
}

// ComputeScore mirrors Python compute_score_matrix: per-check floor by worst
// severity, per-dimension min, weight-averaged overall, A–F grade.
func ComputeScore(results []CheckResult) Score {
	checkScores := map[string]int{}
	for _, r := range results {
		s := 100
		for _, f := range r.Findings {
			switch f.Severity {
			case CRITICAL:
				s = min(s, 0)
			case WARNING:
				s = min(s, 50)
			case INFO:
				s = min(s, 80)
			}
		}
		checkScores[r.Name] = s
	}

	matrix := map[string]int{}
	for dim, checks := range dimensionChecks {
		m := 100
		for _, c := range checks {
			if v, ok := checkScores[c]; ok && v < m {
				m = v
			}
		}
		matrix[dim] = m
	}

	weightedSum, totalWeight := 0, 0
	for dim, w := range dimensionWeights {
		weightedSum += matrix[dim] * w
		totalWeight += w
	}
	overall := 0
	if totalWeight > 0 {
		overall = (weightedSum + totalWeight/2) / totalWeight // round-half-up like Python round()
	}

	return Score{Matrix: matrix, Score: overall, Grade: grade(overall)}
}

func grade(overall int) string {
	switch {
	case overall >= 90:
		return "A"
	case overall >= 75:
		return "B"
	case overall >= 50:
		return "C"
	case overall >= 25:
		return "D"
	default:
		return "F"
	}
}
