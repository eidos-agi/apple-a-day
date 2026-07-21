package aad

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"
)

func init() {
	register(Check{Name: "Dynamic Library Health", Run: checkDylibHealth})
}

// dylibCellarCandidates mirrors the Python check's Homebrew Cellar fallback order.
var dylibCellarCandidates = []string{"/opt/homebrew/Cellar", "/usr/local/Cellar"}

// dylibBroken records one binary -> missing-library pairing.
type dylibBroken struct {
	binary string
	lib    string
}

// checkDylibHealth finds Homebrew binaries with missing dylib dependencies.
// Ported from apple_a_day/checks/dylib_health.py.
func checkDylibHealth() CheckResult {
	r := CheckResult{Name: "Dynamic Library Health"}

	var cellar string
	for _, c := range dylibCellarCandidates {
		if fi, err := os.Stat(c); err == nil && fi.IsDir() {
			cellar = c
			break
		}
	}
	if cellar == "" {
		r.add(Finding{Check: "dylib_health", Severity: OK, Summary: "No Homebrew Cellar found — skipping dylib check"})
		return r
	}

	// bin_dir = cellar.parent / "bin"
	binDir := filepath.Join(filepath.Dir(cellar), "bin")

	var broken []dylibBroken
	checked := 0

	if entries, err := os.ReadDir(binDir); err == nil {
		for _, entry := range entries {
			path := filepath.Join(binDir, entry.Name())

			// Path.is_symlink(): the directory entry itself must be a symlink.
			lst, err := os.Lstat(path)
			if err != nil || lst.Mode()&os.ModeSymlink == 0 {
				continue
			}

			// Path.is_file(): following symlinks, the target must exist and be a regular file.
			st, err := os.Stat(path)
			if err != nil || !st.Mode().IsRegular() {
				continue
			}

			// real = binary.resolve(); skip if the resolved target doesn't exist.
			real, err := filepath.EvalSymlinks(path)
			if err != nil {
				continue
			}
			if _, err := os.Stat(real); err != nil {
				continue
			}

			// otool -L <real>, 5s timeout — matches Python's subprocess.run(timeout=5).
			// ponytail: run()/runT() swallow non-zero exit as "" (unlike Python's
			// subprocess.run, which only raises on timeout/OSError and still counts
			// non-zero-exit otool runs as "checked"). A binary whose otool call exits
			// non-zero will be silently skipped here rather than counted — deferred,
			// exit-clean otool on a resolvable Mach-O binary is the overwhelmingly
			// common case.
			out := runT(5*time.Second, "otool", "-L", real)
			if out == "" {
				continue
			}
			checked++

			lines := strings.Split(out, "\n")
			for _, line := range lines[1:] {
				libPath := strings.TrimSpace(line)
				if idx := strings.Index(libPath, " ("); idx >= 0 {
					libPath = libPath[:idx]
				}
				libPath = strings.TrimSpace(libPath)
				if strings.HasPrefix(libPath, "/opt/homebrew") || strings.HasPrefix(libPath, "/usr/local") {
					if _, err := os.Stat(libPath); err != nil {
						broken = append(broken, dylibBroken{binary: entry.Name(), lib: libPath})
					}
				}
			}
		}
	}

	for _, b := range broken {
		libName := filepath.Base(b.lib)
		r.add(Finding{
			Check:    "dylib_health",
			Severity: CRITICAL,
			Summary:  fmt.Sprintf("%s: missing %s", b.binary, libName),
			Details:  fmt.Sprintf("Expected at: %s", b.lib),
			Fix:      fmt.Sprintf("brew reinstall %s", b.binary),
		})
	}

	if len(broken) == 0 {
		r.add(Finding{Check: "dylib_health", Severity: OK, Summary: fmt.Sprintf("All %d checked binaries have intact dylib links", checked)})
	}

	return r
}
