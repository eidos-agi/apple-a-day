package aad

import (
	"encoding/json"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"time"
)

// Faithful port of apple_a_day/checks/cleanup.py — read-only. This check only
// reports uninstall/disable candidates; it never deletes, moves, or mutates
// anything (no rm, no launchctl bootout, no plist writes).
func init() {
	register(Check{Name: "Cleanup", Run: checkCleanup})
}

// cleanupSafeBundlePrefixes mirrors Python _SAFE_BUNDLE_PREFIXES.
var cleanupSafeBundlePrefixes = []string{"com.apple.", "com.microsoft.Office", "com.google.Chrome"}

// cleanupSafeApps mirrors Python _SAFE_APPS.
var cleanupSafeApps = map[string]bool{
	"Safari": true, "Finder": true, "System Settings": true, "System Preferences": true,
	"App Store": true, "Terminal": true, "Console": true, "Activity Monitor": true,
	"Disk Utility": true, "Migration Assistant": true, "Boot Camp Assistant": true,
	"Font Book": true, "Keychain Access": true, "Screenshot": true, "Preview": true,
	"TextEdit": true, "Calculator": true, "Music": true, "Photos": true, "Maps": true,
	"Messages": true, "FaceTime": true, "Mail": true, "Calendar": true, "Contacts": true,
	"Notes": true, "Reminders": true, "Freeform": true, "Shortcuts": true, "Clock": true,
	"Home": true, "Stocks": true, "Weather": true, "News": true, "Podcasts": true,
	"TV": true, "Books": true, "Voice Memos": true, "QuickTime Player": true,
}

// ponytail: storage.py's storage_guardrail() (fleet storage-tier config at
// ~/.config/eidos/storage-tiers.json, "..storage" system) is not ported yet —
// this check uses a fixed guardrail string matching the Python default output.
// Upgrade to the real tier-aware guidance once storage.py is ported to Go.
const cleanupGuardrail = "STORAGE RULE: work docs → M-Files (aic-m-files), never delete to free disk. " +
	"Caches/Docker → delete locally. Archives → MacMiniStorage only. " +
	"Run `aad reclaim-plan --json` before bulk deletes."

// cleanupApp is one stale-app scoring candidate. Mirrors the Python scored dict.
type cleanupApp struct {
	name     string
	path     string
	bundleID string
	lastUsed string
	daysAgo  int
	hasAgent bool
	sizeMB   int
	score    float64
}

// cleanupOrphanedAgent is a LaunchAgent whose parent app/binary is gone.
type cleanupOrphanedAgent struct {
	label  string
	plist  string
	reason string
}

// cleanupCrashLoopAgent is a LaunchAgent stuck in a crash loop.
type cleanupCrashLoopAgent struct {
	label    string
	exitCode int
	plist    string
	restarts string
}

func checkCleanup() CheckResult {
	r := CheckResult{Name: "Cleanup"}

	staleApps := cleanupFindStaleApps()
	orphanedAgents := cleanupFindOrphanedAgents()
	crashLooping := cleanupFindCrashLoopingAgents()

	// --- Stale apps ---
	if len(staleApps) > 0 {
		var strong, moderate []cleanupApp
		for _, a := range staleApps {
			switch {
			case a.score >= 0.25:
				strong = append(strong, a)
			case a.score > 0.1 && a.score < 0.25:
				moderate = append(moderate, a)
			}
		}

		if len(strong) > 0 {
			top := strong
			if len(top) > 8 {
				top = top[:8]
			}
			names := make([]string, len(top))
			for i, a := range top {
				names[i] = a.name
			}
			shown := names
			if len(shown) > 5 {
				shown = shown[:5]
			}
			ellipsis := ""
			if len(names) > 5 {
				ellipsis = "..."
			}
			var details strings.Builder
			for i, a := range top {
				if i > 0 {
					details.WriteByte('\n')
				}
				fmt.Fprintf(&details, "  %-35s last used: %-20s score: %.2f", a.name, a.lastUsed, a.score)
			}
			r.add(Finding{
				Check:    "cleanup",
				Severity: INFO,
				Summary:  fmt.Sprintf("%d app(s) not used in 90+ days: %s%s", len(strong), strings.Join(shown, ", "), ellipsis),
				Details:  details.String(),
				Fix: "Review and uninstall unused apps. Drag to Trash or use " +
					"`sudo rm -rf /Applications/<App>.app`. " + cleanupGuardrail,
			})
		}

		if len(moderate) > 0 {
			top := moderate
			if len(top) > 5 {
				top = top[:5]
			}
			names := make([]string, len(top))
			for i, a := range top {
				names[i] = a.name
			}
			var details strings.Builder
			for i, a := range top {
				if i > 0 {
					details.WriteByte('\n')
				}
				fmt.Fprintf(&details, "  %-35s last used: %-20s score: %.2f", a.name, a.lastUsed, a.score)
			}
			r.add(Finding{
				Check:    "cleanup",
				Severity: INFO,
				Summary:  fmt.Sprintf("%d app(s) rarely used: %s", len(moderate), strings.Join(names, ", ")),
				Details:  details.String(),
			})
		}
	}

	// --- Orphaned launch agents ---
	if len(orphanedAgents) > 0 {
		top := orphanedAgents
		if len(top) > 10 {
			top = top[:10]
		}
		var details strings.Builder
		for i, a := range top {
			if i > 0 {
				details.WriteByte('\n')
			}
			fmt.Fprintf(&details, "  %-50s → %s", a.label, a.reason)
		}
		r.add(Finding{
			Check:    "cleanup",
			Severity: WARNING,
			Summary:  fmt.Sprintf("%d orphaned launch agent(s) — app removed but agent persists", len(orphanedAgents)),
			Details:  details.String(),
			Fix:      "Remove orphaned plists: `launchctl bootout gui/$(id -u) <plist_path>` then delete the file",
		})
	}

	// --- Crash-looping agents (high annoyance, should disable) ---
	if len(crashLooping) > 0 {
		top := crashLooping
		if len(top) > 5 {
			top = top[:5]
		}
		var details strings.Builder
		for i, a := range top {
			if i > 0 {
				details.WriteByte('\n')
			}
			fmt.Fprintf(&details, "  %-50s exit=%d  restarts=%s", a.label, a.exitCode, a.restarts)
		}
		r.add(Finding{
			Check:    "cleanup",
			Severity: WARNING,
			Summary:  fmt.Sprintf("%d launch agent(s) stuck in crash loops — wasting CPU", len(crashLooping)),
			Details:  details.String(),
			Fix:      "Disable with: `launchctl bootout gui/$(id -u) <plist_path>` — fix or remove the underlying app",
		})
	}

	if len(r.Findings) == 0 {
		r.add(Finding{Check: "cleanup", Severity: OK, Summary: "No obvious cleanup candidates found"})
	}

	return r
}

// cleanupAppGlobs mirrors Python's glob.glob("/Applications/*.app") +
// glob.glob(os.path.expanduser("~/Applications/*.app")).
func cleanupAppGlobs() []string {
	var apps []string
	if m, err := filepath.Glob("/Applications/*.app"); err == nil {
		apps = append(apps, m...)
	}
	if home, err := os.UserHomeDir(); err == nil && home != "" {
		if m, err := filepath.Glob(filepath.Join(home, "Applications", "*.app")); err == nil {
			apps = append(apps, m...)
		}
	}
	return apps
}

// ponytail: this walks every installed app calling mdls + du unconditionally
// (before the 30-day recency skip), same as the Python original. Known perf
// hotspot on machines with many apps — left as-is for fidelity; optimize by
// checking recency before shelling out to du if it becomes a bottleneck.
func cleanupFindStaleApps() []cleanupApp {
	apps := cleanupAppGlobs()
	now := time.Now()
	procCPU := cleanupProcCPUMap()

	var scored []cleanupApp
	for _, appPath := range apps {
		name := strings.TrimSuffix(filepath.Base(appPath), ".app")

		if cleanupSafeApps[name] {
			continue
		}
		bundleID := cleanupBundleID(appPath)
		if bundleID != "" {
			skip := false
			for _, p := range cleanupSafeBundlePrefixes {
				if strings.HasPrefix(bundleID, p) {
					skip = true
					break
				}
			}
			if skip {
				continue
			}
		}

		daysAgo := 999
		lastUsedRaw := cleanupLastUsed(appPath)
		if lastUsedRaw != "" {
			normalized := strings.Replace(lastUsedRaw, " +0000", "+00:00", 1)
			if t, err := time.Parse("2006-01-02 15:04:05-07:00", normalized); err == nil {
				daysAgo = int(now.Sub(t) / (24 * time.Hour))
			}
		}

		sizeMB := cleanupDirSizeMB(appPath)

		if daysAgo < 30 {
			continue
		}

		r := math.Min(float64(daysAgo)/365.0, 1.0)
		u := math.Max(0, 1.0-(float64(daysAgo)/180.0))

		hasAgent := false
		if bundleID != "" {
			hasAgent = cleanupHasAgent(bundleID)
		}
		s := 0.0
		if hasAgent {
			s = 1.0
		}

		cpuPct := procCPU[strings.ToLower(name)]
		p := math.Min(cpuPct/100.0, 1.0)

		k := 0.6*u + 0.4*(1-r)
		a := 0.4*0 + 0.4*p + 0.2*s
		c := a - k + 0.3*r

		if c > 0.1 {
			lastUsed := "never"
			if daysAgo < 999 {
				lastUsed = fmt.Sprintf("%dd ago", daysAgo)
			}
			scored = append(scored, cleanupApp{
				name:     name,
				path:     appPath,
				bundleID: bundleID,
				lastUsed: lastUsed,
				daysAgo:  daysAgo,
				hasAgent: hasAgent,
				sizeMB:   sizeMB,
				score:    math.Round(c*1000) / 1000,
			})
		}
	}

	sort.SliceStable(scored, func(i, j int) bool { return scored[i].score > scored[j].score })
	return scored
}

// cleanupFindOrphanedAgents mirrors Python _find_orphaned_agents: LaunchAgents
// whose parent app is no longer installed. Read-only — never touches the plists.
func cleanupFindOrphanedAgents() []cleanupOrphanedAgent {
	var orphaned []cleanupOrphanedAgent

	home, err := os.UserHomeDir()
	if err != nil || home == "" {
		return orphaned
	}
	agentDir := filepath.Join(home, "Library", "LaunchAgents")
	entries, err := os.ReadDir(agentDir)
	if err != nil {
		return orphaned
	}

	installedBundles := map[string]bool{}
	for _, appPath := range cleanupAppGlobs() {
		if bid := cleanupBundleID(appPath); bid != "" {
			installedBundles[bid] = true
		}
	}

	for _, e := range entries {
		name := e.Name()
		if filepath.Ext(name) != ".plist" {
			continue
		}
		if name == "_disabled" {
			continue
		}

		label := strings.TrimSuffix(name, ".plist")
		if strings.HasPrefix(label, "com.apple.") {
			continue
		}

		plistPath := filepath.Join(agentDir, name)
		plist, ok := cleanupReadPlist(plistPath)
		if !ok {
			continue
		}

		allPaths := cleanupPlistProgramPaths(plist)

		binaryMissing := false
		for _, p := range allPaths {
			if strings.HasPrefix(p, "/") {
				if _, err := os.Stat(p); os.IsNotExist(err) {
					orphaned = append(orphaned, cleanupOrphanedAgent{
						label:  label,
						plist:  plistPath,
						reason: "binary missing: " + p,
					})
					binaryMissing = true
					break
				}
			}
		}
		if binaryMissing {
			continue
		}

		parts := strings.Split(label, ".")
		if len(parts) >= 3 {
			possibleBundle := strings.Join(parts[:3], ".")
			if !strings.HasPrefix(possibleBundle, "com.apple.") &&
				!strings.HasPrefix(possibleBundle, "homebrew.") &&
				!installedBundles[possibleBundle] {
				for _, p := range allPaths {
					if idx := strings.Index(p, "/Applications/"); idx >= 0 {
						rest := p[idx+len("/Applications/"):]
						appRef := rest
						if slash := strings.Index(rest, "/"); slash >= 0 {
							appRef = rest[:slash]
						}
						if _, err := os.Stat(filepath.Join("/Applications", appRef)); os.IsNotExist(err) {
							orphaned = append(orphaned, cleanupOrphanedAgent{
								label:  label,
								plist:  plistPath,
								reason: "app uninstalled: " + appRef,
							})
							break
						}
					}
				}
			}
		}
	}

	return orphaned
}

// cleanupFindCrashLoopingAgents mirrors Python _find_crash_looping_agents.
func cleanupFindCrashLoopingAgents() []cleanupCrashLoopAgent {
	var looping []cleanupCrashLoopAgent

	out := runT(10*time.Second, "launchctl", "list")
	if out == "" {
		return looping
	}
	lines := strings.Split(strings.TrimSpace(out), "\n")
	if len(lines) <= 1 {
		return looping
	}

	home, herr := os.UserHomeDir()

	for _, line := range lines[1:] {
		parts := strings.Split(line, "\t")
		if len(parts) < 3 {
			continue
		}
		pid, status, label := parts[0], parts[1], parts[2]

		if strings.HasPrefix(label, "com.apple.") {
			continue
		}

		if pid == "-" && status != "0" && status != "" {
			exitCode, err := strconv.Atoi(status)
			if err != nil {
				continue
			}

			if herr != nil || home == "" {
				continue
			}
			plistPath := filepath.Join(home, "Library", "LaunchAgents", label+".plist")
			if _, err := os.Stat(plistPath); os.IsNotExist(err) {
				continue
			}

			plist, ok := cleanupReadPlist(plistPath)
			if !ok {
				continue
			}

			shouldFlag := false
			switch ka := plist["KeepAlive"].(type) {
			case bool:
				shouldFlag = ka
			case map[string]interface{}:
				if se, ok := ka["SuccessfulExit"].(bool); ok && !se {
					shouldFlag = true
				}
			}

			if shouldFlag {
				looping = append(looping, cleanupCrashLoopAgent{
					label:    label,
					exitCode: exitCode,
					plist:    plistPath,
					restarts: "continuous",
				})
			}
		}
	}

	return looping
}

// cleanupDirSizeMB gets directory size in MB via `du -sk` (fast, no recursive walk).
func cleanupDirSizeMB(path string) int {
	out := runT(5*time.Second, "du", "-sk", path)
	if out == "" {
		return 0
	}
	fields := strings.Fields(out)
	if len(fields) == 0 {
		return 0
	}
	kb, err := strconv.ParseInt(fields[0], 10, 64)
	if err != nil {
		return 0
	}
	return int(math.Round(float64(kb) / 1024.0))
}

// cleanupLastUsed reads kMDItemLastUsedDate from Spotlight metadata.
func cleanupLastUsed(appPath string) string {
	out := runT(5*time.Second, "mdls", "-name", "kMDItemLastUsedDate", "-raw", appPath)
	val := strings.TrimSpace(out)
	if val == "" || val == "(null)" {
		return ""
	}
	return val
}

// cleanupBundleID reads CFBundleIdentifier from an app's Info.plist.
func cleanupBundleID(appPath string) string {
	plistPath := filepath.Join(appPath, "Contents", "Info.plist")
	if _, err := os.Stat(plistPath); err != nil {
		return ""
	}
	plist, ok := cleanupReadPlist(plistPath)
	if !ok {
		return ""
	}
	if bid, ok := plist["CFBundleIdentifier"].(string); ok {
		return bid
	}
	return ""
}

// cleanupHasAgent checks whether an app (by bundle ID) has a matching LaunchAgent.
func cleanupHasAgent(bundleID string) bool {
	home, err := os.UserHomeDir()
	if err != nil || home == "" {
		return false
	}
	agentDir := filepath.Join(home, "Library", "LaunchAgents")
	entries, err := os.ReadDir(agentDir)
	if err != nil {
		return false
	}
	prefix := strings.ToLower(bundleID)
	for _, e := range entries {
		name := e.Name()
		if filepath.Ext(name) != ".plist" {
			continue
		}
		stem := strings.ToLower(strings.TrimSuffix(name, ".plist"))
		if strings.HasPrefix(stem, prefix) {
			return true
		}
	}
	return false
}

// cleanupReadPlist converts a plist (binary or XML) to JSON via `plutil` and
// parses it. Read-only: `-o -` writes to stdout, never mutates the source file.
func cleanupReadPlist(path string) (map[string]interface{}, bool) {
	out := runT(5*time.Second, "plutil", "-convert", "json", "-o", "-", path)
	if out == "" {
		return nil, false
	}
	var parsed map[string]interface{}
	if err := json.Unmarshal([]byte(out), &parsed); err != nil {
		return nil, false
	}
	return parsed, true
}

// cleanupPlistProgramPaths extracts ProgramArguments + Program from a parsed
// LaunchAgent plist, mirroring Python's `prog_args + ([program] if program else [])`.
func cleanupPlistProgramPaths(plist map[string]interface{}) []string {
	var paths []string
	if pa, ok := plist["ProgramArguments"].([]interface{}); ok {
		for _, v := range pa {
			if s, ok := v.(string); ok {
				paths = append(paths, s)
			}
		}
	}
	if prog, ok := plist["Program"].(string); ok && prog != "" {
		paths = append(paths, prog)
	}
	return paths
}

// cleanupProcCPUMap gets current CPU usage by process name (lowercase),
// mirroring Python _get_process_cpu_map via `ps -eo pcpu,comm`.
func cleanupProcCPUMap() map[string]float64 {
	cpuMap := map[string]float64{}
	out := runT(5*time.Second, "ps", "-eo", "pcpu,comm")
	if out == "" {
		return cpuMap
	}
	lines := strings.Split(strings.TrimSpace(out), "\n")
	if len(lines) <= 1 {
		return cpuMap
	}
	for _, line := range lines[1:] {
		trimmed := strings.TrimSpace(line)
		if trimmed == "" {
			continue
		}
		fields := strings.Fields(trimmed)
		if len(fields) < 2 {
			continue
		}
		cpu, err := strconv.ParseFloat(fields[0], 64)
		if err != nil {
			continue
		}
		idx := strings.Index(trimmed, fields[0]) + len(fields[0])
		comm := strings.TrimSpace(trimmed[idx:])
		name := comm
		if slash := strings.LastIndex(comm, "/"); slash >= 0 {
			name = comm[slash+1:]
		}
		name = strings.ToLower(name)
		cpuMap[name] += cpu
	}
	return cpuMap
}
