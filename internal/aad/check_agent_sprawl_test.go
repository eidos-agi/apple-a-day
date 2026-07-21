package aad

import (
	"strings"
	"testing"
)

func TestSprawlKillPlan(t *testing.T) {
	keep, kill := sprawlKillPlan([]int{7789, 21794, 84874, 43972})
	if keep != 84874 {
		t.Errorf("keep: got %d want 84874 (highest PID = newest)", keep)
	}
	if len(kill) != 3 || kill[0] != 7789 || kill[2] != 43972 {
		t.Errorf("kill: got %v want [7789 21794 43972]", kill)
	}

	if keep, kill := sprawlKillPlan(nil); keep != 0 || kill != nil {
		t.Errorf("empty: got %d/%v want 0/nil", keep, kill)
	}
}

func TestSprawlDedupeFix(t *testing.T) {
	fix := sprawlDedupeFix(
		[]string{"/repo/a/mcp_server.py", "/repo/b/mcp_server.py"},
		map[string][]int{
			"/repo/a/mcp_server.py": {100, 300, 200},
			"/repo/b/mcp_server.py": {400}, // no dupes → no line
		},
	)
	if !strings.Contains(fix, "keep 300 (newest), review-then-kill 100, 200") {
		t.Errorf("missing kill plan line, got:\n%s", fix)
	}
	if strings.Contains(fix, "keep 400") {
		t.Errorf("single-PID script must not get a kill line, got:\n%s", fix)
	}
	// The advisory guardrails must always be present — aad never auto-kills.
	for _, must := range []string{"human approval", "PPID 1", "never auto-kill"} {
		if !strings.Contains(fix, must) {
			t.Errorf("fix text missing %q", must)
		}
	}
}
