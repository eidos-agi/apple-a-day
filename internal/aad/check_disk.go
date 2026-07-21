package aad

import (
	"fmt"
	"strconv"
	"strings"
)

func init() {
	register(Check{Name: "Disk Health", Run: checkDiskHealth})
}

func checkDiskHealth() CheckResult {
	r := CheckResult{Name: "Disk Health"}

	// diskutil reports real APFS container usage — df lies about free space.
	diskBytes, freeBytes := diskUsage()
	if diskBytes == 0 || freeBytes == 0 {
		r.Errors = append(r.Errors, CheckError{
			Check: "disk_health", ErrorCode: "PARSE_ERROR",
			Message: "could not parse diskutil disk size / free space",
		})
		return r
	}

	usedPct := int((1 - float64(freeBytes)/float64(diskBytes)) * 100)
	freeGB := float64(freeBytes) / 1e9
	minFree, _ := loadStorageTiers(defaultTiersPath())

	sev := diskSeverity(freeGB, usedPct, minFree)

	summary := fmt.Sprintf("Boot disk %d%% full — %.1f GB free", usedPct, freeGB)
	if freeGB < minFree {
		summary += fmt.Sprintf(" (below %.0f GB floor)", minFree)
	}
	fix := ""
	if sev != OK {
		// ponytail: snapshot-thinning was the old one-size-fits-all fix; it
		// reclaims ~nothing when only OS-update snapshots exist. Point agents
		// at the ranked plan instead.
		fix = "Run `aad reclaim-plan --json` for ranked reclaim candidates (all require human approval)."
	}
	r.add(Finding{
		Check: "disk_health", Severity: sev,
		Summary: summary,
		Fix:     fix,
	})
	return r
}

// diskSeverity grades free space against the configured hot-tier floor
// (storage-tiers.json min_free_gb, default 50). A near-full disk close to the
// floor is CRITICAL even when the floor itself is not yet breached — agents
// need the stop signal before the floor is blown, not after.
func diskSeverity(freeGB float64, usedPct int, minFreeGB float64) Severity {
	switch {
	case freeGB < 10 || usedPct >= 95:
		return CRITICAL
	case freeGB < minFreeGB:
		return CRITICAL
	case usedPct >= 90 && freeGB < 1.5*minFreeGB:
		return CRITICAL
	case freeGB < 1.5*minFreeGB || usedPct >= 85:
		return WARNING
	default:
		return OK
	}
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
