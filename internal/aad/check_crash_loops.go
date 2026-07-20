package aad

import (
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

func init() {
	register(Check{Name: "Crash Loops", Run: checkCrashLoops})
}

// crashLoopsReportDirs mirrors Python REPORT_DIRS: ~/Library/Logs/DiagnosticReports
// and /Library/Logs/DiagnosticReports.
func crashLoopsReportDirs() []string {
	dirs := []string{"/Library/Logs/DiagnosticReports"}
	if home, err := os.UserHomeDir(); err == nil && home != "" {
		dirs = append([]string{filepath.Join(home, "Library/Logs/DiagnosticReports")}, dirs...)
	}
	return dirs
}

// crashLoopsExtensions mirrors Python CRASH_EXTENSIONS.
var crashLoopsExtensions = map[string]bool{".ips": true, ".crash": true}

// crashLoopsHours mirrors the Python check_crash_loops(hours: int = 24) default.
// ponytail: the ..context/..storage-driven configurable window is deferred; fixed 24h default only.
const crashLoopsHours = 24

// crashLoopsProcessName mirrors Python's
// `f.stem.rsplit("-", 4)[0] if f.stem.count("-") >= 4 else f.stem`.
// Filename format: ProcessName-YYYY-MM-DD-HHMMSS.ips
func crashLoopsProcessName(stem string) string {
	fields := strings.Split(stem, "-")
	dashes := len(fields) - 1
	if dashes < 4 {
		return stem
	}
	return strings.Join(fields[:len(fields)-4], "-")
}

type crashLoopsCount struct {
	process string
	count   int
}

func checkCrashLoops() CheckResult {
	r := CheckResult{Name: "Crash Loops"}
	hours := crashLoopsHours
	cutoff := time.Now().Add(-time.Duration(hours) * time.Hour)

	counts := map[string]int{}
	var order []string // first-seen order, to keep most_common's stable-sort semantics

	for _, dir := range crashLoopsReportDirs() {
		entries, err := os.ReadDir(dir)
		if err != nil {
			continue
		}
		for _, e := range entries {
			name := e.Name()
			ext := filepath.Ext(name)
			if !crashLoopsExtensions[ext] {
				continue
			}
			info, err := e.Info()
			if err != nil {
				continue
			}
			if info.ModTime().Before(cutoff) {
				continue
			}
			stem := strings.TrimSuffix(name, ext)
			process := crashLoopsProcessName(stem)
			if _, seen := counts[process]; !seen {
				order = append(order, process)
			}
			counts[process]++
		}
	}

	items := make([]crashLoopsCount, 0, len(order))
	for _, p := range order {
		items = append(items, crashLoopsCount{process: p, count: counts[p]})
	}
	sort.SliceStable(items, func(i, j int) bool { return items[i].count > items[j].count })

	for _, it := range items {
		var sev Severity
		switch {
		case it.count >= 10:
			sev = CRITICAL
		case it.count >= 3:
			sev = WARNING
		default:
			sev = INFO
		}

		r.add(Finding{
			Check:    "crash_loops",
			Severity: sev,
			Summary:  fmt.Sprintf("%s crashed %d times in the last %dh", it.process, it.count, hours),
			Details:  "Crash reports found in DiagnosticReports directories.",
			Fix: fmt.Sprintf("Check: `log show --predicate 'process == \"%s\"' --last %dh` or reinstall the service.",
				it.process, hours),
		})
	}

	if len(r.Findings) == 0 {
		r.add(Finding{
			Check:    "crash_loops",
			Severity: OK,
			Summary:  fmt.Sprintf("No crash loops detected in the last %dh", hours),
		})
	}

	return r
}
