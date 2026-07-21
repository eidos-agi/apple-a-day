package aad

import (
	"fmt"
	"strconv"
	"strings"
)

// ponytail: profile-aware swap thresholds (swap_thresholds scaled to RAM) and
// docker/ollama fix hints deferred; fixed default bands ported. Upgrade to
// context-scaled bands when the profile subsystem is ported.
func init() {
	register(Check{Name: "Memory Pressure", Run: checkMemoryPressure})
}

const swapWarnMB = 1024.0
const swapCritMB = 4096.0

func checkMemoryPressure() CheckResult {
	r := CheckResult{Name: "Memory Pressure"}

	// Pressure level. Modern macOS memory_pressure -Q prints only a free
	// percentage (no normal/warn/critical token), which read as "unknown"
	// forever — the memorystatus sysctl is authoritative (1/2/4); the string
	// match stays as fallback for older output formats.
	qOut := run("/usr/bin/memory_pressure", "-Q")
	level, sev := pressureLevel(run("sysctl", "-n", "kern.memorystatus_vm_pressure_level"), qOut)
	if qOut != "" || level != "unknown" {
		fix := ""
		if sev != OK && sev != INFO {
			fix = "Close memory-heavy apps or check for leaks with `leaks <pid>`"
		}
		r.add(Finding{
			Check: "memory_pressure", Severity: sev,
			Summary: "Memory pressure: " + level,
			Details: lastLine(qOut),
			Fix:     fix,
		})
	}

	// Swap usage.
	if out := run("sysctl", "vm.swapusage"); strings.Contains(out, "used = ") {
		usedStr := strings.SplitN(strings.SplitN(out, "used = ", 2)[1], " ", 2)[0]
		if used, err := strconv.ParseFloat(strings.TrimSuffix(usedStr, "M"), 64); err == nil {
			sev := OK
			switch {
			case used > swapCritMB:
				sev = CRITICAL
			case used > swapWarnMB:
				sev = WARNING
			}
			fix := ""
			if sev != OK {
				fix = "Reboot to clear swap, then find the memory hog — you're running on SSD, not RAM."
			}
			r.add(Finding{
				Check: "memory_pressure", Severity: sev,
				Summary: "Swap usage: " + usedStr,
				Details: strings.TrimSpace(out),
				Fix:     fix,
			})
		}
	}

	// Wired memory — pinned RAM that intensifies swap pressure.
	if out := run("vm_stat"); out != "" {
		pageSize := 16384 // Apple Silicon default
		var wiredPages int64
		for _, line := range strings.Split(out, "\n") {
			if strings.Contains(line, "page size of") {
				if n, err := strconv.Atoi(strings.TrimSpace(between(line, "page size of", "bytes"))); err == nil {
					pageSize = n
				}
			}
			if strings.HasPrefix(strings.TrimSpace(line), "Pages wired down") {
				v := strings.TrimSuffix(strings.TrimSpace(strings.SplitN(line, ":", 2)[1]), ".")
				wiredPages, _ = strconv.ParseInt(v, 10, 64)
			}
		}
		wiredGB := float64(wiredPages) * float64(pageSize) / (1 << 30)
		ramGB := totalRAMGB()
		if ramGB > 0 && wiredGB > ramGB*0.25 {
			r.add(Finding{
				Check: "memory_pressure", Severity: WARNING,
				Summary: fmt.Sprintf("Wired memory: %.1f GB (%d pages)", wiredGB, wiredPages),
				Details: "High wired memory pins kernel/drivers — leaves less room for apps before swapping.",
				Fix:     "Reboot clears wired pages; then reduce Docker/VM/browser memory footprint.",
			})
		}
	}

	return r
}

// pressureLevel maps kern.memorystatus_vm_pressure_level (1 normal, 2 warning,
// 4 critical) to a verdict, falling back to token-matching memory_pressure -Q
// output when the sysctl is unavailable.
func pressureLevel(sysctlVal, qOut string) (string, Severity) {
	switch strings.TrimSpace(sysctlVal) {
	case "1":
		return "normal", OK
	case "2":
		return "WARNING", WARNING
	case "4":
		return "CRITICAL", CRITICAL
	}
	lower := strings.ToLower(qOut)
	switch {
	case strings.Contains(lower, "critical"):
		return "CRITICAL", CRITICAL
	case strings.Contains(lower, "warn"):
		return "WARNING", WARNING
	case strings.Contains(lower, "normal"):
		return "normal", OK
	}
	return "unknown", INFO
}

func totalRAMGB() float64 {
	if v := run("sysctl", "-n", "hw.memsize"); v != "" {
		if b, err := strconv.ParseInt(v, 10, 64); err == nil {
			return float64(b) / (1 << 30)
		}
	}
	return 16
}

func lastLine(s string) string {
	lines := strings.Split(strings.TrimRight(s, "\n"), "\n")
	return lines[len(lines)-1]
}

func between(s, start, end string) string {
	i := strings.Index(s, start)
	if i < 0 {
		return ""
	}
	rest := s[i+len(start):]
	if j := strings.Index(rest, end); j >= 0 {
		return rest[:j]
	}
	return rest
}
