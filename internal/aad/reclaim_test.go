package aad

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestLoadStorageTiers(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "storage-tiers.json")
	os.WriteFile(path, []byte(`{
		"tiers": [{"id": "hot", "min_free_gb": 50}, {"id": "cold", "path": "/Volumes/X"}],
		"rules": ["Caches/Docker cruft → delete on laptop."]
	}`), 0o644)

	minFree, rules := loadStorageTiers(path)
	if minFree != 50 {
		t.Errorf("min_free_gb: got %v want 50", minFree)
	}
	if len(rules) != 1 {
		t.Errorf("rules: got %d want 1", len(rules))
	}

	// Missing file → safe defaults, never a crash.
	minFree, rules = loadStorageTiers(filepath.Join(dir, "nope.json"))
	if minFree != 50 || rules != nil {
		t.Errorf("defaults: got %v/%v want 50/nil", minFree, rules)
	}
}

// diskSeverity is the storage gate: floor breach and near-full-near-floor are
// CRITICAL (agents must stop writing), approach is WARNING.
func TestDiskSeverity(t *testing.T) {
	cases := []struct {
		free    float64
		usedPct int
		want    Severity
	}{
		{200, 50, OK},      // plenty of room
		{57, 94, CRITICAL}, // the 2026-07-21 baseline: 94% full near floor — old code said WARNING
		{45, 80, CRITICAL}, // below 50 GB floor
		{8, 70, CRITICAL},  // hard floor regardless of config
		{70, 86, WARNING},  // approaching: <1.5x floor
		{100, 86, WARNING}, // high used pct alone
		{80, 92, WARNING},  // 92% used but 80 GB free ≥ 1.5x floor — room to work, not an emergency
	}
	for _, c := range cases {
		if got := diskSeverity(c.free, c.usedPct, 50); got != c.want {
			t.Errorf("diskSeverity(%v, %d): got %v want %v", c.free, c.usedPct, got, c.want)
		}
	}
}

func TestGuardrailText(t *testing.T) {
	if got := guardrailText([]string{"Rule one.", "Rule two."}); !strings.Contains(got, "Rule one. Rule two.") || !strings.Contains(got, "reclaim-plan") {
		t.Errorf("configured rules not rendered: %q", got)
	}
	if got := guardrailText(nil); !strings.Contains(got, "M-Files") || !strings.Contains(got, "reclaim-plan") {
		t.Errorf("fallback guardrail wrong: %q", got)
	}
}

func TestReclaimPlanShape(t *testing.T) {
	plan := BuildReclaimPlan()

	// Real-probe plan on any Mac: JSON round-trips, items sorted largest-first,
	// every item has a command and requires approval (aad never auto-deletes).
	b, err := json.Marshal(plan)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	var back ReclaimPlan
	if err := json.Unmarshal(b, &back); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	for i, it := range plan.Items {
		if it.Command == "" {
			t.Errorf("item %q has no command", it.Item)
		}
		if !it.ApprovalNeeded {
			t.Errorf("item %q must require approval", it.Item)
		}
		if i > 0 && plan.Items[i-1].EstGB < it.EstGB {
			t.Errorf("items not sorted desc at %d (%v < %v)", i, plan.Items[i-1].EstGB, it.EstGB)
		}
	}
	if plan.MinFreeGB <= 0 {
		t.Errorf("min_free_gb missing: %v", plan.MinFreeGB)
	}
}
