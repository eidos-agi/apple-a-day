package aad

import (
	"fmt"
	"regexp"
	"strings"
	"time"
)

func init() {
	register(Check{Name: "Shutdown Causes", Run: checkShutdownCauses})
}

// shutdownCausesRe pulls the numeric cause code out of a "log show" compact
// line, e.g. "... Previous shutdown cause: -128 ...".
var shutdownCausesRe = regexp.MustCompile(`Previous shutdown cause:\s*(-?\d+)`)

// shutdownCausesInfo is the (label, severity) pair for a known cause code.
// https://support.apple.com/en-us/102758
type shutdownCausesInfo struct {
	label string
	sev   Severity
}

var shutdownCausesMap = map[string]shutdownCausesInfo{
	"3":    {"clean reboot", OK},
	"5":    {"clean shutdown (power button)", OK},
	"7":    {"sleep wake failure or CPU watchdog", WARNING},
	"0":    {"power restored after outage", INFO},
	"-1":   {"kernel panic", CRITICAL},
	"-2":   {"kernel panic (watchdog)", CRITICAL},
	"-3":   {"thermal emergency shutdown", CRITICAL},
	"-62":  {"bridgeOS crash (T2/firmware)", CRITICAL},
	"-64":  {"low battery emergency shutdown", WARNING},
	"-71":  {"SOC watchdog", CRITICAL},
	"-74":  {"temperature too high", CRITICAL},
	"-104": {"battery health failure", WARNING},
	"-128": {"unknown cause (forced power off?)", WARNING},
}

// shutdownCausesEntry is one (timestamp, code) pair pulled from logs/sysctl.
type shutdownCausesEntry struct {
	ts, code string
}

// checkShutdownCauses analyzes recent shutdown reasons from system logs.
// Faithful port of apple_a_day/checks/shutdown_causes.py.
func checkShutdownCauses() CheckResult {
	r := CheckResult{Name: "Shutdown Causes"}

	// Method 1: log show for shutdown cause entries over the last 7 days.
	var causes []shutdownCausesEntry
	if raw := runT(30*time.Second, "log", "show",
		"--predicate", `eventMessage contains "Previous shutdown cause"`,
		"--style", "compact",
		"--last", "7d",
	); raw != "" {
		for _, line := range strings.Split(strings.TrimSpace(raw), "\n") {
			m := shutdownCausesRe.FindStringSubmatch(line)
			if m == nil {
				continue
			}
			ts := ""
			if f := strings.Fields(line); len(f) > 0 {
				ts = f[0]
			}
			causes = append(causes, shutdownCausesEntry{ts: ts, code: m[1]})
		}
	}

	// Method 2: sysctl for the last shutdown cause (always available).
	if len(causes) == 0 {
		if out := runT(5*time.Second, "sysctl", "-n", "kern.shutdownreason"); out != "" {
			causes = append(causes, shutdownCausesEntry{ts: "last boot", code: strings.TrimSpace(out)})
		}
	}

	if len(causes) == 0 {
		r.add(Finding{
			Check: "shutdown_causes", Severity: OK,
			Summary: "No recent shutdown events found in logs",
		})
		return r
	}

	// Analyze causes.
	type shutdownCausesAbnormal struct {
		ts, code, label string
		sev             Severity
	}
	var abnormal []shutdownCausesAbnormal
	for _, c := range causes {
		label, sev := shutdownCausesLabel(c.code)
		if sev == CRITICAL || sev == WARNING {
			abnormal = append(abnormal, shutdownCausesAbnormal{c.ts, c.code, label, sev})
		}
	}

	if len(abnormal) > 0 {
		worst := abnormal[0]
		for _, a := range abnormal[1:] {
			if a.sev > worst.sev {
				worst = a
			}
		}

		var details strings.Builder
		for _, a := range abnormal {
			fmt.Fprintf(&details, "  %s: cause %s (%s)\n", a.ts, a.code, a.label)
		}
		if len(causes) > len(abnormal) {
			fmt.Fprintf(&details, "  + %d clean shutdown(s)\n", len(causes)-len(abnormal))
		}

		r.add(Finding{
			Check: "shutdown_causes", Severity: worst.sev,
			Summary: fmt.Sprintf("%d abnormal shutdown(s) in the last 7 days — worst: %s", len(abnormal), worst.label),
			Details: strings.TrimRight(details.String(), "\n"),
			Fix:     shutdownCausesFix(worst.code),
		})
	} else {
		r.add(Finding{
			Check: "shutdown_causes", Severity: OK,
			Summary: fmt.Sprintf("All %d recent shutdown(s) were clean", len(causes)),
		})
	}

	return r
}

// shutdownCausesLabel looks up the (label, severity) for a cause code,
// defaulting to an "unknown code" INFO finding for unmapped codes.
func shutdownCausesLabel(code string) (string, Severity) {
	if v, ok := shutdownCausesMap[code]; ok {
		return v.label, v.sev
	}
	return fmt.Sprintf("unknown code %s", code), INFO
}

// shutdownCausesFix returns a targeted fix suggestion for a shutdown cause code.
func shutdownCausesFix(code string) string {
	switch code {
	case "-1":
		return "Kernel panic — run `aad checkup -c kernel_panics` for details. " +
			"Check for bad RAM, faulty peripherals, or kext issues."
	case "-2":
		return "Watchdog-triggered kernel panic — a subsystem hung for too long. " +
			"Check for stuck I/O (external drives, network mounts)."
	case "-3":
		return "Thermal emergency — Mac shut down to prevent hardware damage. " +
			"Check fans, vents, and ambient temperature. " +
			"Run `aad checkup -c thermal` for current thermal state."
	case "-74":
		return "Temperature sensor triggered shutdown. " +
			"Same as thermal emergency — check cooling and workload."
	case "-62":
		return "bridgeOS/T2 crash — firmware issue. Check for macOS updates."
	case "-71":
		return "SOC watchdog — Apple Silicon subsystem timeout. Check for macOS updates."
	case "-64":
		return "Battery ran out. Check battery health in System Information."
	case "-104":
		return "Battery health triggered shutdown. Check battery cycle count and consider replacement."
	case "-128":
		return "Forced power off — either user held power button or system lost power. " +
			"If you didn't do this, check power supply and sleep/wake issues."
	case "7":
		return "Sleep/wake failure — Mac couldn't wake properly. " +
			"Check for peripherals that interfere with sleep, or disable Power Nap."
	default:
		return "Investigate the shutdown cause code in Console.app or `log show`."
	}
}
