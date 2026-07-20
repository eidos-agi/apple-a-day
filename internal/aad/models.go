// Package aad is the Go rewrite of apple-a-day: read-only macOS health checks.
// Faithful port of the Python apple_a_day package; the Python version stays as
// the reference oracle until the Go binary reaches checkup parity.
package aad

// Severity ranks a finding. Order matters: OK < INFO < WARNING < CRITICAL.
type Severity int

const (
	OK Severity = iota
	INFO
	WARNING
	CRITICAL
)

func (s Severity) String() string {
	switch s {
	case OK:
		return "ok"
	case INFO:
		return "info"
	case WARNING:
		return "warning"
	case CRITICAL:
		return "critical"
	}
	return "unknown"
}

// Icon mirrors the Python Finding.icon glyphs.
func (s Severity) Icon() string {
	switch s {
	case OK:
		return "✓"
	case INFO:
		return "ℹ"
	case WARNING:
		return "⚠"
	case CRITICAL:
		return "✗"
	}
	return "?"
}

// Finding is a single health finding.
type Finding struct {
	Check    string   `json:"check"`
	Severity Severity `json:"severity"`
	Summary  string   `json:"summary"`
	Details  string   `json:"details,omitempty"`
	Fix      string   `json:"fix,omitempty"`
}

// CheckError is a structured error when a check itself fails to run.
type CheckError struct {
	Check      string `json:"check"`
	ErrorCode  string `json:"error_code"`
	Message    string `json:"message"`
	Suggestion string `json:"suggestion,omitempty"`
}

// CheckResult is the output of one check module.
type CheckResult struct {
	Name     string       `json:"name"`
	Findings []Finding    `json:"findings"`
	Errors   []CheckError `json:"errors,omitempty"`
}

// add appends a finding; keeps check bodies terse.
func (r *CheckResult) add(f Finding) { r.Findings = append(r.Findings, f) }

// WorstSeverity returns the highest severity across findings (OK if none).
func (r CheckResult) WorstSeverity() Severity {
	worst := OK
	for _, f := range r.Findings {
		if f.Severity > worst {
			worst = f.Severity
		}
	}
	return worst
}
