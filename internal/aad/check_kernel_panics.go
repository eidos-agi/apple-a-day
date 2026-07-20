package aad

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"time"
)

// Faithful port of apple_a_day/checks/kernel_panics.py.
func init() {
	register(Check{Name: "Kernel Panics", Run: checkKernelPanics})
}

const kernelPanicsDir = "/Library/Logs/DiagnosticReports"

// kernelPanicsDays mirrors the Python default `days: int = 7`; every caller in
// apple_a_day/checks/__init__.py invokes check_kernel_panics() with no args,
// so the default is the only behavior exercised in practice.
const kernelPanicsDays = 7

// kernelPanicsPattern preserves Python dict insertion order (3.7+ dicts are
// ordered) so the first-match-wins semantics of the `for pattern, desc in
// KNOWN_PANIC_PATTERNS.items()` loop are faithfully reproduced.
type kernelPanicsPattern struct {
	pattern string
	desc    string
}

var kernelPanicsKnownPatterns = []kernelPanicsPattern{
	{"watchdog timeout", "System froze — a core process couldn't check in. Usually caused by a hung driver or runaway service."},
	{"hibernate_is_resume", "Mac panicked while going to sleep or waking up. Hibernate image was corrupted."},
	{"iBoot panic", "Low-level boot firmware panic — often a failed hibernate resume."},
	{"kernel memory", "Kernel ran out of memory. Check for memory-hungry processes."},
	{"zone map exhaustion", "Kernel zone allocator exhausted. Too many open files or network connections."},
}

// kernelPanicsBody is the subset of the panic report JSON body we care about.
type kernelPanicsBody struct {
	PanicString string `json:"panicString"`
	Date        string `json:"date"`
}

// kernelPanicsFile pairs a panic report path with its mtime for sorting.
type kernelPanicsFile struct {
	path  string
	mtime time.Time
}

func checkKernelPanics() CheckResult {
	r := CheckResult{Name: "Kernel Panics"}

	info, err := os.Stat(kernelPanicsDir)
	if err != nil || !info.IsDir() {
		r.add(Finding{Check: "kernel_panics", Severity: OK, Summary: "No panic report directory found"})
		return r
	}

	matches, err := filepath.Glob(filepath.Join(kernelPanicsDir, "panic-*.panic"))
	if err != nil {
		r.Errors = append(r.Errors, CheckError{
			Check: "kernel_panics", ErrorCode: "glob_failed", Message: err.Error(),
		})
		return r
	}

	cutoff := time.Now().Add(-time.Duration(kernelPanicsDays) * 24 * time.Hour)
	var panicFiles []kernelPanicsFile
	for _, m := range matches {
		fi, err := os.Stat(m)
		if err != nil {
			continue
		}
		if fi.ModTime().Before(cutoff) {
			continue
		}
		panicFiles = append(panicFiles, kernelPanicsFile{path: m, mtime: fi.ModTime()})
	}

	// Sort by mtime, most recent first (Python: key=mtime, reverse=True).
	sort.Slice(panicFiles, func(i, j int) bool { return panicFiles[i].mtime.After(panicFiles[j].mtime) })

	if len(panicFiles) == 0 {
		r.add(Finding{Check: "kernel_panics", Severity: OK, Summary: "No kernel panics in the last " + strconv.Itoa(kernelPanicsDays) + " days"})
		return r
	}

	for _, pf := range panicFiles {
		raw, err := os.ReadFile(pf.path)
		if err != nil {
			r.add(Finding{
				Check: "kernel_panics", Severity: WARNING,
				Summary: "Unparseable panic report: " + filepath.Base(pf.path),
				Fix:     "Manually review: " + pf.path,
			})
			continue
		}

		// Panic files may have a JSON header line + JSON body; the Python code
		// splits on the first newline and parses whichever half is present.
		text := string(raw)
		var jsonPart string
		if idx := strings.IndexByte(text, '\n'); idx >= 0 {
			jsonPart = text[idx+1:]
		} else {
			jsonPart = text
		}

		var body kernelPanicsBody
		if err := json.Unmarshal([]byte(jsonPart), &body); err != nil {
			r.add(Finding{
				Check: "kernel_panics", Severity: WARNING,
				Summary: "Unparseable panic report: " + filepath.Base(pf.path),
				Fix:     "Manually review: " + pf.path,
			})
			continue
		}

		// Python: body.get("date", "unknown") — default fires only when the key
		// is absent. Go's zero-value string can't distinguish "absent" from
		// "present but empty"; panic reports always populate date, so this
		// collapses both to "unknown" without changing observed behavior.
		date := body.Date
		if date == "" {
			date = "unknown"
		}

		explanation := "Unknown panic type — review the full report."
		lowerPanic := strings.ToLower(body.PanicString)
		for _, kp := range kernelPanicsKnownPatterns {
			if strings.Contains(lowerPanic, strings.ToLower(kp.pattern)) {
				explanation = kp.desc
				break
			}
		}

		r.add(Finding{
			Check: "kernel_panics", Severity: CRITICAL,
			Summary: "Kernel panic on " + date,
			Details: explanation,
			Fix:     "Full report: " + pf.path,
		})
	}

	return r
}
