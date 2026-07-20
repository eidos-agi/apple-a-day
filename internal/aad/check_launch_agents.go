package aad

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

// launchAgentsDirs mirrors AGENT_DIRS in the Python check: the LaunchAgent /
// LaunchDaemon plist directories scanned for KeepAlive crash-loop risk.
func launchAgentsDirs() []string {
	dirs := []string{
		"/Library/LaunchAgents",
		"/Library/LaunchDaemons",
	}
	if home, err := os.UserHomeDir(); err == nil && home != "" {
		dirs = append([]string{filepath.Join(home, "Library/LaunchAgents")}, dirs...)
	}
	return dirs
}

func init() {
	register(Check{Name: "Launch Agents", Run: checkLaunchAgents})
}

// launchAgentsCrashed is one launchctl-reported service that exited non-zero
// while not currently running (pid == "-").
type launchAgentsCrashed struct {
	label  string
	status int
}

// launchAgentsKeepAlive is one plist-declared KeepAlive service.
type launchAgentsKeepAlive struct {
	label string
	path  string
}

func checkLaunchAgents() CheckResult {
	r := CheckResult{Name: "Launch Agents"}

	// Get list of services and their status.
	out := run("launchctl", "list")
	if out == "" {
		r.add(Finding{Check: "launch_agents", Severity: INFO, Summary: "Could not query launchctl"})
		return r
	}

	// Parse launchctl output: PID Status Label (skip header line).
	var crashed []launchAgentsCrashed
	lines := strings.Split(out, "\n")
	if len(lines) > 0 {
		lines = lines[1:]
	}
	for _, line := range lines {
		parts := strings.Split(line, "\t")
		if len(parts) < 3 {
			continue
		}
		pid, statusStr, label := parts[0], parts[1], parts[2]
		statusCode, err := strconv.Atoi(statusStr)
		if err != nil {
			continue
		}
		if statusCode != 0 && pid == "-" {
			crashed = append(crashed, launchAgentsCrashed{label: label, status: statusCode})
		}
	}

	// Also scan plist files for KeepAlive services (crash loop risk).
	var keepAlive []launchAgentsKeepAlive
	for _, dir := range launchAgentsDirs() {
		entries, err := os.ReadDir(dir)
		if err != nil {
			continue
		}
		for _, entry := range entries {
			name := entry.Name()
			if entry.IsDir() || strings.HasPrefix(name, ".") || !strings.HasSuffix(name, ".plist") {
				continue
			}
			path := filepath.Join(dir, name)
			label, isKeepAlive := launchAgentsParsePlist(path)
			if label == "" {
				label = strings.TrimSuffix(name, ".plist")
			}
			if isKeepAlive {
				keepAlive = append(keepAlive, launchAgentsKeepAlive{label: label, path: path})
			}
		}
	}

	// Cross-reference: KeepAlive + crashed = crash loop.
	crashedStatusByLabel := map[string]int{}
	crashedLabels := map[string]bool{}
	for _, c := range crashed {
		crashedLabels[c.label] = true
		if _, ok := crashedStatusByLabel[c.label]; !ok {
			crashedStatusByLabel[c.label] = c.status // first match, matching Python's next(...)
		}
	}
	for _, k := range keepAlive {
		if status, ok := crashedStatusByLabel[k.label]; ok {
			r.add(Finding{
				Check:    "launch_agents",
				Severity: CRITICAL,
				Summary:  fmt.Sprintf("%s: crash-looping (KeepAlive + exit code %d)", k.label, status),
				Details:  "Plist: " + k.path,
				Fix:      launchAgentsCrashLoopFix(k.path),
			})
		}
	}

	// Report other crashed services (non-KeepAlive, less severe), capped at 10.
	keepAliveLabels := map[string]bool{}
	for _, k := range keepAlive {
		keepAliveLabels[k.label] = true
	}
	capped := crashed
	if len(capped) > 10 {
		capped = capped[:10]
	}
	for _, c := range capped {
		if !keepAliveLabels[c.label] {
			r.add(Finding{
				Check:    "launch_agents",
				Severity: INFO,
				Summary:  fmt.Sprintf("%s: exited with status %d", c.label, c.status),
			})
		}
	}

	hasSevere := false
	for _, f := range r.Findings {
		if f.Severity == CRITICAL || f.Severity == WARNING {
			hasSevere = true
			break
		}
	}
	if !hasSevere {
		r.Findings = append([]Finding{{
			Check:    "launch_agents",
			Severity: OK,
			Summary:  "No crash-looping launch agents detected",
		}}, r.Findings...)
	}

	return r
}

// launchAgentsParsePlist reads a launchd plist via `plutil -convert json -o -`
// (stdlib has no plist decoder; plutil is a macOS-native, always-present tool,
// so this avoids hand-rolling a bplist/XML plist parser). Returns the Label
// (empty if absent) and whether KeepAlive is truthy — matching Python's
// `plist.get("Label", stem)` / `keep_alive and keep_alive is not False`,
// which reduces to plain truthiness since False is already falsy.
func launchAgentsParsePlist(path string) (label string, keepAlive bool) {
	out := run("plutil", "-convert", "json", "-o", "-", path)
	if out == "" {
		return "", false
	}
	var plist map[string]json.RawMessage
	if err := json.Unmarshal([]byte(out), &plist); err != nil {
		return "", false
	}
	if raw, ok := plist["Label"]; ok {
		json.Unmarshal(raw, &label)
	}
	if raw, ok := plist["KeepAlive"]; ok {
		keepAlive = launchAgentsTruthy(raw)
	}
	return label, keepAlive
}

// launchAgentsTruthy mimics Python truthiness for a decoded plist value:
// bool uses its own value; a dict (object) is truthy iff non-empty; anything
// else (number, string, array) is treated as falsy since KeepAlive never
// legitimately takes those shapes.
func launchAgentsTruthy(raw json.RawMessage) bool {
	var v interface{}
	if err := json.Unmarshal(raw, &v); err != nil {
		return false
	}
	switch t := v.(type) {
	case bool:
		return t
	case map[string]interface{}:
		return len(t) > 0
	default:
		return false
	}
}

// launchAgentsCrashLoopFix mirrors crash_loop_fix() from ..context. The
// Python version branches on ctx["is_ai_user"] to add agent-workflow-aware
// advice for AI-user profiles; that profile lookup lives in ..context, which
// is out of scope for this port.
// ponytail: is_ai_user profile branch deferred — always returns the
// non-AI-user fix text (fixed default) rather than reading ../context.
func launchAgentsCrashLoopFix(plistPath string) string {
	baseFix := fmt.Sprintf("Stop with: `launchctl bootout gui/$(id -u) %s`", plistPath)
	return baseFix + "\nOr fix the underlying issue and restart."
}
