package aad

import (
	"fmt"
	"runtime"
	"strings"
	"sync"
	"time"
)

// Check is one registered health check. Name is the display name that appears
// in CheckResult; Run performs the check. Mirrors the Python check_* functions.
type Check struct {
	Name  string
	Run   func() CheckResult
	OptIn bool // not run by default; selectable via -c
}

// registry holds every check. Checks self-register via register() in init().
var registry []Check

func register(c Check) { registry = append(registry, c) }

// Registry returns the registered checks (default set unless includeOptIn).
func Registry(includeOptIn bool) []Check {
	out := make([]Check, 0, len(registry))
	for _, c := range registry {
		if c.OptIn && !includeOptIn {
			continue
		}
		out = append(out, c)
	}
	return out
}

// CheckupReport is the full result of a checkup.
type CheckupReport struct {
	Results    []CheckResult  `json:"results"`
	DurationMS int64          `json:"duration_ms"`
	MacInfo    map[string]any `json:"mac_info"`
}

// selectChecks filters by name (case-insensitive, "check_" prefix optional).
func selectChecks(names []string) []Check {
	if len(names) == 0 {
		return Registry(false)
	}
	want := map[string]bool{}
	for _, n := range names {
		want[strings.ToLower(n)] = true
	}
	var out []Check
	for _, c := range Registry(true) {
		n := strings.ToLower(c.Name)
		if want[n] || want[strings.ReplaceAll(n, " ", "_")] {
			out = append(out, c)
		}
	}
	return out
}

// RunCheckup executes the selected checks (all default checks if names is nil).
// Checks run concurrently (bounded) since they're independent I/O-bound calls.
func RunCheckup(parallel bool, names []string) CheckupReport {
	start := time.Now()
	checks := selectChecks(names)
	results := make([]CheckResult, len(checks))

	runOne := func(i int, c Check) {
		defer func() {
			if p := recover(); p != nil {
				results[i] = CheckResult{
					Name: c.Name,
					Errors: []CheckError{{
						Check: c.Name, ErrorCode: "UNKNOWN_ERROR",
						Message:    fmt.Sprint(p),
						Suggestion: "Run the check individually to see full output",
					}},
				}
			}
		}()
		results[i] = c.Run()
	}

	if parallel {
		var wg sync.WaitGroup
		sem := make(chan struct{}, min(6, max(1, len(checks))))
		for i, c := range checks {
			wg.Add(1)
			go func(i int, c Check) {
				defer wg.Done()
				sem <- struct{}{}
				defer func() { <-sem }()
				runOne(i, c)
			}(i, c)
		}
		wg.Wait()
	} else {
		for i, c := range checks {
			runOne(i, c)
		}
	}

	// results are index-ordered to match registration already.
	return CheckupReport{
		Results:    results,
		DurationMS: time.Since(start).Milliseconds(),
		MacInfo:    macInfo(),
	}
}

func macInfo() map[string]any {
	info := map[string]any{
		"arch":     runtime.GOARCH,
		"hostname": run("hostname"),
	}
	if v := run("sw_vers", "-productVersion"); v != "" {
		info["os_version"] = v
	}
	if cpu := run("sysctl", "-n", "machdep.cpu.brand_string"); cpu != "" {
		info["cpu"] = cpu
	}
	return info
}
