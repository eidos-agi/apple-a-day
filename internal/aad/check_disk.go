package aad

import (
	"fmt"
	"strconv"
	"strings"
)

// ponytail: profile-aware refinements (developer 50GB floor, m_files tiers,
// snapshot relief guidance) deferred — core free-space verdict ported first.
func init() {
	register(Check{Name: "Disk Health", Run: checkDiskHealth})
}

func checkDiskHealth() CheckResult {
	r := CheckResult{Name: "Disk Health"}

	// diskutil reports real APFS container usage — df lies about free space.
	out := run("diskutil", "info", "/")
	if out == "" {
		r.Errors = append(r.Errors, CheckError{
			Check: "disk_health", ErrorCode: "TOOL_NOT_FOUND",
			Message: "diskutil info / returned nothing",
		})
		return r
	}

	info := map[string]string{}
	for _, line := range strings.Split(out, "\n") {
		if k, v, ok := strings.Cut(line, ":"); ok {
			info[strings.TrimSpace(k)] = strings.TrimSpace(v)
		}
	}

	diskBytes := parseBytesField(info["Disk Size"])
	freeBytes := parseBytesField(info["Container Free Space"])
	if diskBytes == 0 || freeBytes == 0 {
		r.Errors = append(r.Errors, CheckError{
			Check: "disk_health", ErrorCode: "PARSE_ERROR",
			Message: "could not parse disk size / free space",
		})
		return r
	}

	usedPct := int((1 - float64(freeBytes)/float64(diskBytes)) * 100)
	freeGB := float64(freeBytes) / 1e9

	sev := OK
	switch {
	case freeGB < 10:
		sev = CRITICAL
	case freeGB < 30:
		sev = WARNING
	case usedPct >= 95:
		sev = CRITICAL
	case usedPct >= 85:
		sev = WARNING
	}

	fix := ""
	if sev != OK {
		fix = "Run `sudo tmutil thinlocalsnapshots / 9999999999 1` to reclaim snapshot space."
	}
	r.add(Finding{
		Check: "disk_health", Severity: sev,
		Summary: fmt.Sprintf("Boot disk %d%% full — %.1f GB free", usedPct, freeGB),
		Fix:     fix,
	})
	return r
}

// parseBytesField extracts the byte count from a diskutil field like
// "994.7 GB (994662584320 Bytes)". Returns 0 if absent.
func parseBytesField(raw string) int64 {
	i := strings.Index(raw, "(")
	j := strings.Index(raw, " Bytes")
	if i < 0 || j < 0 || j <= i+1 {
		return 0
	}
	n, err := strconv.ParseInt(strings.TrimSpace(raw[i+1:j]), 10, 64)
	if err != nil {
		return 0
	}
	return n
}
