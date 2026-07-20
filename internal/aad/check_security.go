package aad

import (
	"os"
	"strings"
)

func init() {
	register(Check{Name: "Security", Run: checkSecurity})
}

// checkSecurity mirrors security.py check_security(): SIP, Gatekeeper,
// FileVault, and XProtect status.
func checkSecurity() CheckResult {
	r := CheckResult{Name: "Security"}

	// SIP (System Integrity Protection).
	if out := run("csrutil", "status"); out != "" {
		lower := strings.ToLower(out)
		switch {
		case strings.Contains(lower, "enabled"):
			r.add(Finding{Check: "security", Severity: OK, Summary: "System Integrity Protection: enabled"})
		case strings.Contains(lower, "disabled"):
			r.add(Finding{
				Check: "security", Severity: CRITICAL,
				Summary: "System Integrity Protection: DISABLED",
				Details: "SIP protects core system files from modification. Disabling it exposes your Mac to rootkits and malware.",
				Fix:     "Reboot into Recovery Mode (hold Power button), open Terminal, run: csrutil enable",
			})
		default:
			r.add(Finding{Check: "security", Severity: INFO, Summary: "SIP status unclear: " + securityTruncate(out, 80)})
		}
	}

	// Gatekeeper.
	// ponytail: Python concatenates stdout+stderr for spctl --status; shared
	// run() is stdout-only (per contract, not redefining exec helpers).
	// Verified assessments text lands on stdout on this machine — deferred.
	if out := run("spctl", "--status"); out != "" {
		lower := strings.ToLower(out)
		switch {
		case strings.Contains(lower, "assessments enabled"):
			r.add(Finding{Check: "security", Severity: OK, Summary: "Gatekeeper: enabled"})
		case strings.Contains(lower, "assessments disabled"):
			r.add(Finding{
				Check: "security", Severity: WARNING,
				Summary: "Gatekeeper: disabled",
				Details: "Gatekeeper blocks unnotarized apps. Without it, any downloaded app can run.",
				Fix:     "sudo spctl --master-enable",
			})
		}
	}

	// FileVault.
	if out := run("fdesetup", "status"); out != "" {
		switch {
		case strings.Contains(out, "On"):
			r.add(Finding{Check: "security", Severity: OK, Summary: "FileVault: enabled (disk encryption active)"})
		case strings.Contains(out, "Off"):
			r.add(Finding{
				Check: "security", Severity: WARNING,
				Summary: "FileVault: OFF — disk is not encrypted",
				Details: "If your Mac is lost or stolen, anyone can read your files.",
				Fix:     "System Settings → Privacy & Security → FileVault → Turn On",
			})
		}
	}

	// XProtect version — read directly from bundle plist (instant, no system_profiler).
	// ponytail: Python uses plistlib against the file directly; Go stdlib has no
	// plist parser and the contract forbids adding new deps for a single field,
	// so shell out to plutil (same shared run() helper) to extract the key.
	const xprotectPlist = "/Library/Apple/System/Library/CoreServices/XProtect.bundle/Contents/version.plist"
	if _, err := os.Stat(xprotectPlist); err == nil {
		if version := run("plutil", "-extract", "CFBundleShortVersionString", "raw", "-o", "-", xprotectPlist); version != "" {
			r.add(Finding{
				Check: "security", Severity: OK,
				Summary: "XProtect: version " + version,
				Details: "XProtect updates are applied automatically by macOS.",
			})
		} else {
			r.add(Finding{Check: "security", Severity: OK, Summary: "XProtect: version unknown"})
		}
	} else {
		r.add(Finding{Check: "security", Severity: INFO, Summary: "XProtect: bundle not found at expected path"})
	}

	if len(r.Findings) == 0 {
		r.add(Finding{Check: "security", Severity: INFO, Summary: "Could not determine security status"})
	}

	return r
}

// securityTruncate mirrors Python's `s[:n]` slicing (rune-safe truncation).
func securityTruncate(s string, n int) string {
	runes := []rune(s)
	if len(runes) <= n {
		return s
	}
	return string(runes[:n])
}
