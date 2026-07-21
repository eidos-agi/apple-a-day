package aad

import "testing"

// ComputeScore must match Python compute_score_matrix: per-check floor, per-dim
// min, weighted average, A–F grade.
func TestComputeScore(t *testing.T) {
	// All-clear → 100 / A.
	clean := []CheckResult{{Name: "Disk Health", Findings: []Finding{{Severity: OK}}}}
	if s := ComputeScore(clean); s.Score != 100 || s.Grade != "A" {
		t.Errorf("clean: got %d/%s want 100/A", s.Score, s.Grade)
	}

	// One CRITICAL in Disk Health drops the storage dim to 0; all other dims
	// default to 100. Total weight = 17, so overall = round(1500/17) = 88 → B.
	// Matches Python round(1500/17).
	crit := []CheckResult{{Name: "Disk Health", Findings: []Finding{{Severity: CRITICAL}}}}
	s := ComputeScore(crit)
	if s.Matrix["storage"] != 0 {
		t.Errorf("storage dim: got %d want 0", s.Matrix["storage"])
	}
	if s.Score != 88 || s.Grade != "B" {
		t.Errorf("crit: got %d/%s want 88/B", s.Score, s.Grade)
	}
}
