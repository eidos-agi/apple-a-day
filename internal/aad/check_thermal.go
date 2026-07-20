package aad

import (
	"fmt"
	"strconv"
	"strings"
)

func init() {
	register(Check{Name: "Thermal", Run: checkThermal})
}

// checkThermal assesses thermal pressure and detects CPU throttling.
// Faithful port of apple_a_day/checks/thermal.py.
func checkThermal() CheckResult {
	r := CheckResult{Name: "Thermal"}

	thermalFound := false

	// --- Thermal pressure level ---
	// Try sysctl first (Intel Macs), fall back to pmset (Apple Silicon).
	if raw := run("sysctl", "-n", "kern.thermalpressurelevel"); raw != "" {
		if level, err := strconv.Atoi(strings.TrimSpace(raw)); err == nil {
			thermalFound = true

			var label string
			var sev Severity
			switch level {
			case 0:
				label, sev = "nominal", OK
			case 1:
				label, sev = "moderate", INFO
			case 2:
				label, sev = "heavy", WARNING
			case 3:
				label, sev = "trapping", CRITICAL
			case 4:
				label, sev = "sleeping", CRITICAL
			default:
				label, sev = fmt.Sprintf("unknown (%d)", level), INFO
			}

			fix := ""
			switch sev {
			case CRITICAL:
				fix = "Mac is thermally throttled — CPU speed is reduced to prevent damage. " +
					"Move to a cooler surface, check vents aren't blocked, close heavy apps. " +
					"If persistent, SMC reset: shut down, hold power 10s, release, wait 5s, boot."
			case WARNING:
				fix = "Thermal pressure is elevated — performance may degrade. " +
					"Reduce load or improve airflow."
			}

			r.add(Finding{
				Check: "thermal", Severity: sev,
				Summary: fmt.Sprintf("Thermal pressure: %s", label),
				Details: fmt.Sprintf("kern.thermalpressurelevel = %d", level),
				Fix:     fix,
			})
		}
	}

	// Fallback: pmset -g therm (works on Apple Silicon, where the sysctl
	// above is typically absent).
	if !thermalFound {
		if out := run("pmset", "-g", "therm"); out != "" {
			lower := strings.ToLower(out)
			var sev Severity
			var label string
			switch {
			case strings.Contains(lower, "no thermal warning") && strings.Contains(lower, "no performance warning"):
				sev, label = OK, "nominal"
			case strings.Contains(lower, "performance warning") || strings.Contains(lower, "thermal warning"):
				sev, label = WARNING, "elevated"
			default:
				sev, label = OK, "nominal"
			}

			fix := ""
			if sev == WARNING {
				fix = "Thermal or performance warning active — reduce workload or improve airflow."
			}

			r.add(Finding{
				Check: "thermal", Severity: sev,
				Summary: fmt.Sprintf("Thermal pressure: %s", label),
				Details: strings.TrimSpace(out),
				Fix:     fix,
			})
			thermalFound = true
		}
	}

	if !thermalFound {
		r.add(Finding{
			Check: "thermal", Severity: OK,
			Summary: "Thermal monitoring: no warnings detected",
		})
	}

	// --- kernel_task CPU usage (thermal throttling indicator) ---
	if out := run("ps", "-eo", "pid,pcpu,comm"); out != "" {
		lines := strings.Split(out, "\n")
		for _, line := range lines[1:] {
			parts := strings.Fields(line)
			if len(parts) < 3 {
				continue
			}
			comm := strings.Join(parts[2:], " ")
			if !strings.HasSuffix(strings.TrimSpace(comm), "kernel_task") {
				continue
			}
			cpuPct, err := strconv.ParseFloat(parts[1], 64)
			if err != nil {
				break
			}

			var sev Severity
			var summary string
			switch {
			case cpuPct > 200:
				sev = CRITICAL
				summary = fmt.Sprintf("kernel_task at %.0f%% CPU — Mac is heavily thermal-throttled", cpuPct)
			case cpuPct > 50:
				sev = WARNING
				summary = fmt.Sprintf("kernel_task at %.0f%% CPU — thermal throttling active", cpuPct)
			case cpuPct > 10:
				sev = INFO
				summary = fmt.Sprintf("kernel_task at %.0f%% CPU — mild thermal management", cpuPct)
			default:
				sev = OK
				summary = fmt.Sprintf("kernel_task at %.0f%% CPU — normal", cpuPct)
			}

			fix := ""
			if sev == CRITICAL || sev == WARNING {
				fix = "kernel_task uses CPU to generate idle cycles (heat management). " +
					"Reduce workload, improve ventilation, or use a cooling pad."
			}

			r.add(Finding{
				Check: "thermal", Severity: sev,
				Summary: summary,
				Details: fmt.Sprintf("kernel_task PID %s at %v%% CPU", parts[0], cpuPct),
				Fix:     fix,
			})
			break
		}
	}

	// --- Fan speed (Apple Silicon doesn't always expose this, but try) ---
	// powermetrics requires root; run() swallows the resulting error the same
	// way the Python PermissionError/TimeoutExpired catch does — skip silently.
	// Python used timeout=10, matching run()'s default 10s exactly.
	if out := run("powermetrics", "--samplers", "smc", "-n", "1", "-i", "1"); out != "" && strings.Contains(out, "Fan") {
		for _, line := range strings.Split(out, "\n") {
			if strings.Contains(line, "Fan") && strings.Contains(strings.ToLower(line), "rpm") {
				r.add(Finding{
					Check: "thermal", Severity: INFO,
					Summary: strings.TrimSpace(line),
				})
				break
			}
		}
	}

	if len(r.Findings) == 0 {
		r.add(Finding{
			Check: "thermal", Severity: OK,
			Summary: "Thermal state: normal",
		})
	}

	return r
}
