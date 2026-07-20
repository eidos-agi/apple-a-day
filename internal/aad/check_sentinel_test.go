package aad

import "testing"

// classifySentinel is the branch logic that must stay faithful to the Python
// check: paused > alerts > quiet, and free-GB severity is NOT this check's job.
func TestClassifySentinel(t *testing.T) {
	cases := []struct {
		name string
		in   sentinelStatus
		want Severity
	}{
		{"quiet", sentinelStatus{FreeGB: 40}, OK},
		{"acted", sentinelStatus{FreeGB: 8, RecentAlerts: []string{"cleaned 3GB"}}, INFO},
		{"paused wins over alerts", sentinelStatus{FreeGB: 4, PausedPIDs: []string{"123"}, RecentAlerts: []string{"x"}}, WARNING},
		{"low disk alone is not our severity", sentinelStatus{FreeGB: 2}, OK},
	}
	for _, c := range cases {
		if got := classifySentinel(c.in).Severity; got != c.want {
			t.Errorf("%s: got %v want %v", c.name, got, c.want)
		}
	}
}
