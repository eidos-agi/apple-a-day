package aad

import "testing"

// pressureLevel: sysctl memorystatus level is authoritative; -Q token match is
// the fallback; percentage-only -Q output (macOS 13+) must not read "unknown"
// when the sysctl answered.
func TestPressureLevel(t *testing.T) {
	cases := []struct {
		sysctl, qOut string
		wantLevel    string
		wantSev      Severity
	}{
		{"1", "System-wide memory free percentage: 63%", "normal", OK},
		{"2", "System-wide memory free percentage: 36%", "WARNING", WARNING}, // the macOS 15.3 "unknown" bug case
		{"4", "", "CRITICAL", CRITICAL},
		{"", "The system has normal memory pressure", "normal", OK},   // old-format fallback
		{"garbage", "Status: warn level reached", "WARNING", WARNING}, // fallback on unparsable sysctl
		{"", "System-wide memory free percentage: 50%", "unknown", INFO},
	}
	for _, c := range cases {
		level, sev := pressureLevel(c.sysctl, c.qOut)
		if level != c.wantLevel || sev != c.wantSev {
			t.Errorf("pressureLevel(%q, %q): got %s/%v want %s/%v", c.sysctl, c.qOut, level, sev, c.wantLevel, c.wantSev)
		}
	}
}
