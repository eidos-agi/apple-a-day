package aad

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os/exec"
	"strings"
	"time"
)

func init() {
	register(Check{Name: "Homebrew", Run: checkHomebrew})
}

// checkHomebrew runs brew doctor and checks for orphaned/outdated packages.
// Faithful port of apple_a_day/checks/homebrew.py check_homebrew().
func checkHomebrew() CheckResult {
	r := CheckResult{Name: "Homebrew"}

	// Check if brew exists.
	version := homebrewRun(5*time.Second, "brew", "--version")
	if version.notFound || version.timedOut {
		r.add(Finding{Check: "homebrew", Severity: OK, Summary: "Homebrew not installed — skipping"})
		return r
	}

	// brew doctor
	doctor := homebrewRun(60*time.Second, "brew", "doctor")
	switch {
	case doctor.timedOut:
		r.add(Finding{Check: "homebrew", Severity: INFO, Summary: "brew doctor timed out"})
	case doctor.exitCode != 0:
		var warnings []string
		for _, line := range strings.Split(doctor.stderr, "\n") {
			if strings.HasPrefix(line, "Warning:") {
				warnings = append(warnings, line)
			}
		}
		if len(warnings) > 5 {
			warnings = warnings[:5]
		}
		for _, w := range warnings {
			r.add(Finding{
				Check:    "homebrew",
				Severity: WARNING,
				Summary:  strings.ReplaceAll(w, "Warning: ", ""),
				Fix:      "Run `brew doctor` for full details.",
			})
		}
	default:
		r.add(Finding{Check: "homebrew", Severity: OK, Summary: "brew doctor: all clear"})
	}

	// Outdated packages
	outdated := homebrewRun(30*time.Second, "brew", "outdated", "--json=v2")
	if !outdated.timedOut && outdated.stdout != "" {
		var data struct {
			Formulae []json.RawMessage `json:"formulae"`
			Casks    []json.RawMessage `json:"casks"`
		}
		// ponytail: python leaves json.JSONDecodeError uncaught (would crash the
		// check); we treat a parse failure as "no signal" instead, matching the
		// silent-skip behavior it already applies to timeouts/OSError. Deferred —
		// revisit only if brew ever ships malformed --json=v2 output in practice.
		if err := json.Unmarshal([]byte(outdated.stdout), &data); err == nil {
			total := len(data.Formulae) + len(data.Casks)
			if total > 0 {
				sev := INFO
				if total >= 20 {
					sev = WARNING
				}
				r.add(Finding{
					Check:    "homebrew",
					Severity: sev,
					Summary:  fmt.Sprintf("%d outdated packages (%d formulae, %d casks)", total, len(data.Formulae), len(data.Casks)),
					Fix:      "Run `brew upgrade` to update.",
				})
			}
		}
	}

	return r
}

// homebrewResult carries exit classification the shared run()/runT() helpers
// collapse away (they return "" on any error), which this check needs to
// distinguish "not installed" from "ran and exited non-zero" from "timed out" —
// mirroring the Python subprocess.run() exception/returncode branches.
type homebrewResult struct {
	stdout, stderr string
	exitCode       int
	timedOut       bool
	notFound       bool
}

// homebrewRun runs name/args with a timeout, capturing stdout, stderr, and
// exit classification. Prefixed per collision rule — package aad has 17
// parallel check files.
func homebrewRun(timeout time.Duration, name string, args ...string) homebrewResult {
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()

	cmd := exec.CommandContext(ctx, name, args...)
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	err := cmd.Run()

	res := homebrewResult{
		stdout: strings.TrimRight(stdout.String(), "\n"),
		stderr: stderr.String(),
	}

	if ctx.Err() == context.DeadlineExceeded {
		res.timedOut = true
		return res
	}
	if err == nil {
		return res
	}

	var execErr *exec.Error
	if errors.As(err, &execErr) && errors.Is(execErr.Err, exec.ErrNotFound) {
		res.notFound = true
		return res
	}
	var exitErr *exec.ExitError
	if errors.As(err, &exitErr) {
		res.exitCode = exitErr.ExitCode()
		return res
	}
	// ponytail: any other OSError (e.g. permission denied) is uncaught in the
	// Python version and would crash the check; here we degrade to "not found"
	// so the Go check stays alive. Deferred — revisit only if this masks a real
	// failure mode in practice.
	res.notFound = true
	return res
}
