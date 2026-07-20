package aad

import (
	"fmt"
	"runtime"
	"strconv"
	"strings"
)

func init() {
	register(Check{Name: "CPU Load", Run: checkCPULoad})
}

func checkCPULoad() CheckResult {
	r := CheckResult{Name: "CPU Load"}
	cores := runtime.NumCPU()
	if cores == 0 {
		cores = 8
	}

	// Load average via sysctl: "{ 2.34 2.10 1.98 }".
	if raw := run("sysctl", "-n", "vm.loadavg"); raw != "" {
		f := strings.Fields(strings.Trim(raw, "{} "))
		if len(f) >= 3 {
			l1, _ := strconv.ParseFloat(f[0], 64)
			l5, _ := strconv.ParseFloat(f[1], 64)
			l15, _ := strconv.ParseFloat(f[2], 64)
			ratio := l1 / float64(cores)

			var sev Severity
			var summary string
			switch {
			case ratio > 10:
				sev = CRITICAL
				summary = fmt.Sprintf("Load average %.0f is %.0fx your %d cores — machine is severely overloaded", l1, ratio, cores)
			case ratio > 3:
				sev = WARNING
				summary = fmt.Sprintf("Load average %.0f is %.1fx your %d cores — system is struggling", l1, ratio, cores)
			case ratio > 1.5:
				sev = INFO
				summary = fmt.Sprintf("Load average %.1f is moderately high (%.1fx %d cores)", l1, ratio, cores)
			default:
				sev = OK
				summary = fmt.Sprintf("Load average %.1f — healthy for %d cores", l1, cores)
			}
			fix := ""
			if sev == CRITICAL || sev == WARNING {
				fix = "Identify top processes below and kill or throttle the worst offenders"
				if l15 > float64(cores)*3 {
					fix += fmt.Sprintf(". Load has been high for 15+ minutes (%.0f) — sustained, not a spike", l15)
				} else if l1 > float64(cores)*5 && l15 < float64(cores)*2 {
					fix += ". This looks like a recent spike — may resolve on its own"
				}
			}
			r.add(Finding{
				Check: "cpu_load", Severity: sev, Summary: summary,
				Details: fmt.Sprintf("1m: %.1f  5m: %.1f  15m: %.1f  cores: %d", l1, l5, l15, cores),
				Fix:     fix,
			})
		}
	}

	// Top CPU consumers: ps sorted by CPU desc, stop below 10%.
	if out := run("ps", "-eo", "pid,pcpu,pmem,comm", "-r"); out != "" {
		lines := strings.Split(out, "\n")
		type hog struct {
			pid, name string
			cpu, mem  float64
		}
		var hogs []hog
		for _, line := range lines[1:min(21, len(lines))] {
			parts := strings.Fields(line)
			if len(parts) < 4 {
				continue
			}
			cpu, _ := strconv.ParseFloat(parts[1], 64)
			if cpu < 10 {
				break
			}
			mem, _ := strconv.ParseFloat(parts[2], 64)
			comm := strings.Join(parts[3:], " ")
			name := comm[strings.LastIndex(comm, "/")+1:]
			hogs = append(hogs, hog{parts[0], name, cpu, mem})
		}
		if len(hogs) > 0 {
			total := 0.0
			var details strings.Builder
			for _, h := range hogs {
				total += h.cpu
				tag := categorizeHog(h.name)
				if tag != "" {
					tag = " [" + tag + "]"
				}
				fmt.Fprintf(&details, "  %-30s %5.1f%% CPU  %4.1f%% MEM  (PID %s)%s\n", h.name, h.cpu, h.mem, h.pid, tag)
			}
			sev := INFO
			switch {
			case total > float64(cores)*100*0.8:
				sev = CRITICAL
			case total > float64(cores)*100*0.5:
				sev = WARNING
			}
			r.add(Finding{
				Check: "cpu_load", Severity: sev,
				Summary: fmt.Sprintf("%d process(es) using >10%% CPU (total: %.0f%%)", len(hogs), total),
				Details: strings.TrimRight(details.String(), "\n"),
				Fix:     "Review top consumers — kill or defer non-essential work",
			})
		} else {
			r.add(Finding{Check: "cpu_load", Severity: OK, Summary: "No processes above 10% CPU"})
		}
	}

	return r
}

// categorizeHog tags known process names. Ported from Python _categorize_hogs.
func categorizeHog(name string) string {
	exact := map[string]string{
		"fileproviderd": "cloud-sync", "OneDrive": "cloud-sync", "Dropbox": "cloud-sync",
		"bird": "cloud-sync", "cloudd": "cloud-sync",
		"prl_client_app": "vm", "prl_disp_service": "vm", "prl_vm_app": "vm",
		"VBoxHeadless": "vm", "qemu-system-aarch64": "vm", "com.docker.hyperkit": "vm", "Docker Desktop": "vm",
		"xcodebuild": "build", "clang": "build", "swift": "build", "rustc": "build",
		"cargo": "build", "gcc": "build", "make": "build", "ninja": "build",
		"Google Chrome Helper": "browser", "Safari": "browser", "firefox": "browser",
		"trustd": "system-security", "mds_stores": "spotlight", "mdworker_shared": "spotlight",
		"WindowServer": "system-graphics", "kernel_task": "system-thermal",
		"node": "dev-service", "python3": "dev-service", "uvicorn": "dev-service", "ruby": "dev-service",
		"DeskIn": "remote-desktop", "Screen": "remote-desktop", "iTerm2": "terminal",
		"Codex": "electron-agent", "Comet": "electron-agent",
	}
	if t, ok := exact[name]; ok {
		return t
	}
	switch {
	case strings.Contains(name, "Chrome"):
		return "browser"
	case strings.Contains(name, "Docker"):
		return "vm"
	case strings.Contains(name, "Parallels") || strings.Contains(name, "prl_"):
		return "vm"
	case strings.Contains(name, "mcp_server") || strings.HasPrefix(name, "py:"):
		return "mcp"
	case strings.Contains(strings.ToLower(name), "claude"):
		return "agent-cli"
	}
	return ""
}
