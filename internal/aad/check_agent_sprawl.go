package aad

import (
	"fmt"
	"regexp"
	"sort"
	"strconv"
	"strings"
)

// ponytail: Python's except (TimeoutExpired, OSError) branch reports the exact
// exception text in its INFO finding; run() swallows the underlying error into
// "", so the failure-path message below is generic rather than the real error
// string. Verdict/shape (single INFO finding, early return) is unchanged.
func init() {
	register(Check{Name: "Agent Sprawl", Run: checkAgentSprawl})
}

// agentSprawlMCPPatterns mirrors Python's _MCP_PATTERNS.
var agentSprawlMCPPatterns = []*regexp.Regexp{
	regexp.MustCompile(`mcp_server\.py`),
	regexp.MustCompile(`/mcp_server/`),
	regexp.MustCompile(`py:.*mcp`),
}

// agentSprawlElectronShells mirrors Python's _ELECTRON_SHELLS.
var agentSprawlElectronShells = []string{"Codex", "Comet", "Google Chrome", "Microsoft Teams"}

// agentSprawlPyRef mirrors the `re.search(r"(py:[^\s]+)", args)` fallback in
// Python's _extract_mcp_script.
var agentSprawlPyRef = regexp.MustCompile(`py:\S+`)

func checkAgentSprawl() CheckResult {
	r := CheckResult{Name: "Agent Sprawl"}

	raw := run("ps", "-eo", "pid,comm,args")
	if raw == "" {
		r.add(Finding{
			Check:    "agent_sprawl",
			Severity: INFO,
			Summary:  "Could not inspect processes: ps -eo pid,comm,args failed",
		})
		return r
	}

	lines := strings.Split(strings.TrimSpace(raw), "\n")
	if len(lines) > 0 {
		lines = lines[1:] // drop header row, matches Python's stdout.strip().split("\n")[1:]
	}

	mcpByScript := map[string][]int{}
	mcpCertain := map[string]bool{}
	var scriptOrder []string
	var claudePPIDs []int
	electronCounts := map[string]int{}

	for _, rawLine := range lines {
		line := strings.TrimSpace(rawLine)
		if line == "" {
			continue
		}
		pidS, comm, args, ok := agentSprawlSplit3(line)
		if !ok {
			continue
		}
		pid, err := strconv.Atoi(pidS)
		if err != nil {
			continue
		}

		if script, certain, isServer := agentSprawlClassify(args); isServer {
			if _, seen := mcpByScript[script]; !seen {
				scriptOrder = append(scriptOrder, script)
			}
			mcpByScript[script] = append(mcpByScript[script], pid)
			mcpCertain[script] = mcpCertain[script] || certain
		}

		if strings.Contains(args, "claude") && strings.Contains(" "+args+" ", " -p ") {
			claudePPIDs = append(claudePPIDs, pid)
		}

		for _, shell := range agentSprawlElectronShells {
			if strings.Contains(comm, shell) || strings.Contains(args, shell) {
				electronCounts[shell]++
			}
		}
	}

	// dupes: scripts with more than 2 processes, in first-seen order.
	// Generic (non-mcp-marked) server.py groups only count when duplicated —
	// a single normal server.py app is not sprawl and must not inflate totals.
	var dupeScripts []string
	totalMCP := 0
	for _, s := range scriptOrder {
		if mcpCertain[s] || len(mcpByScript[s]) > 2 {
			totalMCP += len(mcpByScript[s])
		}
		if len(mcpByScript[s]) > 2 {
			dupeScripts = append(dupeScripts, s)
		}
	}

	if len(dupeScripts) > 0 {
		worstScript := dupeScripts[0]
		for _, s := range dupeScripts[1:] {
			if len(mcpByScript[s]) > len(mcpByScript[worstScript]) {
				worstScript = s
			}
		}
		worstPIDs := mcpByScript[worstScript]

		sortedScripts := append([]string(nil), dupeScripts...)
		sort.SliceStable(sortedScripts, func(i, j int) bool {
			return len(mcpByScript[sortedScripts[i]]) > len(mcpByScript[sortedScripts[j]])
		})
		if len(sortedScripts) > 6 {
			sortedScripts = sortedScripts[:6]
		}

		detailLines := make([]string, 0, len(sortedScripts))
		for _, s := range sortedScripts {
			pids := mcpByScript[s]
			trunc := s
			if len(trunc) > 70 {
				trunc = trunc[:70]
			}
			n := len(pids)
			if n > 8 {
				n = 8
			}
			pidStrs := make([]string, 0, n)
			for _, p := range pids[:n] {
				pidStrs = append(pidStrs, strconv.Itoa(p))
			}
			detailLines = append(detailLines, fmt.Sprintf("  %-70s  %d processes  PIDs: %s", trunc, len(pids), strings.Join(pidStrs, ", ")))
		}

		sev := WARNING
		if len(worstPIDs) > 5 {
			sev = CRITICAL
		}
		base := worstScript
		if i := strings.LastIndex(base, "/"); i >= 0 {
			base = base[i+1:]
		}
		r.add(Finding{
			Check:    "agent_sprawl",
			Severity: sev,
			Summary: fmt.Sprintf("%d MCP server processes — %d script(s) duplicated (worst: %d× %s)",
				totalMCP, len(dupeScripts), len(worstPIDs), base),
			Details: strings.Join(detailLines, "\n"),
			Fix:     sprawlDedupeFix(sortedScripts, mcpByScript),
		})
	} else if totalMCP > 8 {
		r.add(Finding{
			Check:    "agent_sprawl",
			Severity: WARNING,
			Summary:  fmt.Sprintf("%d MCP server processes running — high for one user", totalMCP),
			Fix:      "Close unused agent sessions; restart iTerm/Cursor to reap stale MCP servers.",
		})
	}

	if len(claudePPIDs) > 3 {
		n := len(claudePPIDs)
		if n > 12 {
			n = 12
		}
		pidStrs := make([]string, 0, n)
		for _, p := range claudePPIDs[:n] {
			pidStrs = append(pidStrs, strconv.Itoa(p))
		}
		r.add(Finding{
			Check:    "agent_sprawl",
			Severity: WARNING,
			Summary:  fmt.Sprintf("%d parallel `claude -p` subprocesses (session summarizers)", len(claudePPIDs)),
			Details:  "PIDs: " + strings.Join(pidStrs, ", "),
			Fix:      "Session-resume daemons are stacking — pause extra agent tools or restart Claude Code/Codex.",
		})
	}

	var activeElectrons []string
	for shell, count := range electronCounts {
		if count > 0 {
			activeElectrons = append(activeElectrons, shell)
		}
	}
	sort.Strings(activeElectrons)
	if len(activeElectrons) >= 3 {
		parts := make([]string, 0, len(activeElectrons))
		for _, shell := range activeElectrons {
			parts = append(parts, fmt.Sprintf("%s (%d)", shell, electronCounts[shell]))
		}
		r.add(Finding{
			Check:    "agent_sprawl",
			Severity: WARNING,
			Summary:  fmt.Sprintf("%d Electron browser shells active simultaneously", len(activeElectrons)),
			Details:  strings.Join(parts, ", "),
			Fix:      "Pick one browser for agent work (Chrome OR Codex OR Comet) — triple shells tax WindowServer and RAM.",
		})
	}

	if len(r.Findings) == 0 {
		r.add(Finding{
			Check:    "agent_sprawl",
			Severity: OK,
			Summary:  "Agent/MCP process count looks normal",
		})
	}

	return r
}

// sprawlKillPlan splits a dupe script's PIDs into (keep, kill-candidates):
// keep the highest PID — almost always the newest process, i.e. the one bound
// to the live session — and mark the rest for review. ponytail: PID order is a
// heuristic (PIDs wrap); the fix text tells the operator to verify with ps
// before killing, and aad never kills anything itself.
func sprawlKillPlan(pids []int) (keep int, kill []int) {
	if len(pids) == 0 {
		return 0, nil
	}
	kill = append([]int(nil), pids...)
	sort.Ints(kill)
	keep = kill[len(kill)-1]
	return keep, kill[:len(kill)-1]
}

// sprawlDedupeFix renders a per-script safe-dedupe plan for the operator.
// Explicitly advisory: verify orphans (PPID 1 = parent session died) first,
// never kill a PID attached to a live boss/worker session.
func sprawlDedupeFix(scripts []string, mcpByScript map[string][]int) string {
	var b strings.Builder
	b.WriteString("Safe dedupe (advisory — requires human approval, never auto-kill):\n")
	for _, s := range scripts {
		keep, kill := sprawlKillPlan(mcpByScript[s])
		if len(kill) == 0 {
			continue
		}
		base := s
		if i := strings.LastIndex(base, "/"); i >= 0 {
			base = base[i+1:]
		}
		killStrs := make([]string, 0, len(kill))
		for _, p := range kill {
			killStrs = append(killStrs, strconv.Itoa(p))
		}
		fmt.Fprintf(&b, "  %s: keep %d (newest), review-then-kill %s\n", base, keep, strings.Join(killStrs, ", "))
	}
	b.WriteString("Verify before killing: `ps -o pid,ppid,lstart,command -p <PIDs>` — PPID 1 means orphaned (parent session died); a live PPID means an active session, leave the child alone. If most parents are live agent CLIs (grok/codex/claude), the fix is closing idle sessions — each spawns a full MCP set, and killing children while parents live just respawns them.")
	return b.String()
}

// agentSprawlSplit3 mirrors Python's `line.split(None, 2)`: at most 3
// whitespace-delimited fields, where the third field keeps any internal
// whitespace and must be non-empty (Python's `len(parts) < 3` guard).
func agentSprawlSplit3(line string) (pid, comm, args string, ok bool) {
	i := strings.IndexAny(line, " \t")
	if i < 0 {
		return "", "", "", false
	}
	pid = line[:i]
	rest := strings.TrimLeft(line[i:], " \t")
	j := strings.IndexAny(rest, " \t")
	if j < 0 {
		return "", "", "", false
	}
	comm = rest[:j]
	args = strings.TrimLeft(rest[j:], " \t")
	if args == "" {
		return "", "", "", false
	}
	return pid, comm, args, true
}

// agentSprawlClassify decides whether a ps args line is an agent/MCP server.
// certain=true for anything with an mcp marker in the path; certain=false for
// generic */server.py processes, which only count when duplicated (the fleet
// runs MCP servers with no "mcp" in the path — showme/server.py,
// aic-m-files/server.py — but a lone webapp server.py must not match).
func agentSprawlClassify(args string) (script string, certain bool, isServer bool) {
	lower := strings.ToLower(args)
	for _, pat := range agentSprawlMCPPatterns {
		if pat.MatchString(args) {
			return agentSprawlExtractScript(args), true, true
		}
	}
	for _, seg := range []string{"mcp-server", "mcp-servers", "mcp_servers", "/mcp/"} {
		if strings.Contains(lower, seg) {
			return agentSprawlExtractScript(args), true, true
		}
	}
	if tok := agentSprawlServerPyToken(args); tok != "" {
		return tok, strings.Contains(lower, "mcp"), true
	}
	return "", false, false
}

// agentSprawlServerPyToken returns the first */server.py path token, if any.
func agentSprawlServerPyToken(args string) string {
	for _, t := range strings.Fields(args) {
		if strings.HasSuffix(t, "/server.py") {
			return t
		}
	}
	return ""
}

// agentSprawlExtractScript picks the best script token from a ps args line:
// a path-like *.py token first, then anything with an mcp marker, then the
// legacy py: reference, then a truncated arg string.
func agentSprawlExtractScript(args string) string {
	for _, token := range strings.Fields(args) {
		lt := strings.ToLower(token)
		if strings.HasSuffix(lt, ".py") && strings.Contains(token, "/") {
			return token
		}
	}
	for _, token := range strings.Fields(args) {
		lt := strings.ToLower(token)
		if strings.Contains(lt, "mcp_server") || strings.Contains(lt, "mcp-server") || strings.Contains(token, "/mcp") {
			return token
		}
	}
	if m := agentSprawlPyRef.FindString(args); m != "" {
		return m
	}
	if len(args) > 80 {
		return args[:80]
	}
	return args
}
