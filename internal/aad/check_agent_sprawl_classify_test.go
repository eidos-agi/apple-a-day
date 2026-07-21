package aad

import "testing"

// Fixture lines from the 2026-07-21 aad-speed-disk-relief mission inventory —
// the shapes the old patterns missed (pal, keeper, aic-m-files, showme) plus
// the ones they caught (forge-forge, director-daemon).
func TestAgentSprawlClassify(t *testing.T) {
	cases := []struct {
		args        string
		wantScript  string
		wantCertain bool
		wantServer  bool
	}{
		{"/opt/homebrew/bin/python3 /Users/d/repos/pal-mcp-server/server.py", "/Users/d/repos/pal-mcp-server/server.py", true, true},
		{"python /Users/d/mcp-servers/keeper/server.py --stdio", "/Users/d/mcp-servers/keeper/server.py", true, true},
		{"/Users/d/repos-eidos-agi/forge-forge/mcp_server.py", "/Users/d/repos-eidos-agi/forge-forge/mcp_server.py", true, true},
		{"python /Users/d/repos-personal/aic-director-daemon/mcp_server/serve", "/Users/d/repos-personal/aic-director-daemon/mcp_server/serve", true, true},
		// no "mcp" anywhere in path → generic candidate, NOT certain
		{"/Users/d/.cache/uv/builds-v0/.tmp0okpFm/bin/python /Users/d/repos-eidos-agi/showme/server.py", "/Users/d/repos-eidos-agi/showme/server.py", false, true},
		{"python /Users/d/repos-aic/aic-m-files/server.py", "/Users/d/repos-aic/aic-m-files/server.py", false, true},
		// not a server at all
		{"vim notes.md", "", false, false},
		{"python /opt/webapp/app.py", "", false, false},
	}
	for _, c := range cases {
		script, certain, isServer := agentSprawlClassify(c.args)
		if isServer != c.wantServer || certain != c.wantCertain || (c.wantServer && script != c.wantScript) {
			t.Errorf("classify(%q): got (%q, certain=%v, server=%v) want (%q, %v, %v)",
				c.args, script, certain, isServer, c.wantScript, c.wantCertain, c.wantServer)
		}
	}
}

// A single generic server.py must not count as sprawl; duplicated ones must.
// (The totals logic lives inline in checkAgentSprawl; this pins the rule the
// way agents experience it: certain groups always count, generic need >2.)
func TestGenericServerCountRule(t *testing.T) {
	byScript := map[string][]int{
		"/x/pal-mcp-server/server.py": {100},           // certain, single → counts
		"/x/showme/server.py":         {200, 201, 202}, // generic, 3 dupes → counts + dupe
		"/x/webapp/server.py":         {300},           // generic, single → invisible
	}
	certain := map[string]bool{"/x/pal-mcp-server/server.py": true}

	total, dupes := 0, 0
	for s, pids := range byScript {
		if certain[s] || len(pids) > 2 {
			total += len(pids)
		}
		if len(pids) > 2 {
			dupes++
		}
	}
	if total != 4 || dupes != 1 {
		t.Errorf("got total=%d dupes=%d want 4/1", total, dupes)
	}
}

func TestLowRiskTotal(t *testing.T) {
	items := []ReclaimItem{
		{Item: "a", EstGB: 10, Risk: "low — rebuildable"},
		{Item: "b", EstGB: 5.5, Risk: "low — recreatable"},
		{Item: "c", EstGB: 40, Risk: "medium — review first"},
		{Item: "d", EstGB: -1, Risk: "low — but unsized"},
	}
	if got := lowRiskTotal(items); got != 15.5 {
		t.Errorf("lowRiskTotal: got %v want 15.5", got)
	}
}
