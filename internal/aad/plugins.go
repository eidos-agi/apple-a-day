package aad

// Plugins in aad are not a runtime framework — a "plugin" is an external tool or
// daemon (its own repo/lifecycle) that aad surfaces read-only. ACTIVE plugins
// are DISCOVERED: any program that drops a health-contract manifest in
// ~/.config/eidos/health.d/ is found and probed uniformly (see
// health_contract.go) — no per-tool Go. PROPOSED plugins are the ranked roadmap
// below; they carry no manifest until built.
// ponytail: proposed roadmap stays a literal list (it's documentation, not a
// runtime concern); only the active set is dynamic.

type PluginStatus string

const (
	PluginActive   PluginStatus = "active"
	PluginProposed PluginStatus = "proposed"
)

// Plugin is a catalog entry (active = discovered from a manifest; proposed = roadmap).
type Plugin struct {
	Name    string
	Kind    string // "actuator" | "analyst"
	Scope   string // "node" | "fleet"
	Status  PluginStatus
	Tool    string
	Repo    string
	Summary string
	// Health probes an active plugin (liveness + health from its manifest);
	// nil for proposed. Returns (ok, detail).
	Health func() (bool, string)
}

// Plugins returns discovered active plugins (probed via their manifests) plus
// the proposed roadmap, in a stable order (active first, then proposed).
func Plugins() []Plugin {
	var out []Plugin
	for _, m := range DiscoverManifests() {
		m := m // capture for the closure
		out = append(out, Plugin{
			Name: m.Name, Kind: m.Kind, Scope: m.Scope, Status: PluginActive,
			Tool: m.Name, Repo: m.Repo, Summary: m.Summary,
			Health: func() (bool, string) {
				// Daemons: a dead process is down regardless of health. CLI
				// tools declare no liveness — go straight to health.
				if m.HasLiveness() {
					if live, d := m.ProbeLiveness(); !live {
						return false, "down — " + d
					}
				}
				return m.ProbeHealth()
			},
		})
	}
	return append(out, proposedPlugins...)
}

// proposedPlugins — the ranked roadmap (same actuator/analyst shape at the
// next-riskiest domain for a headless, always-on, fleet-critical Mac).
var proposedPlugins = []Plugin{
	{Name: "Conduit", Kind: "actuator", Scope: "fleet", Status: PluginProposed,
		Tool: "conduit", Repo: "eidos-agi/conduit",
		Summary: "Fleet nervous system — ensures every server is online & accessible; aad reports up, conduit covers aad's own-death blind spot."},
	{Name: "Boot Guardian", Kind: "actuator", Scope: "node", Status: PluginProposed,
		Tool: "boot-guardian", Repo: "eidos-agi/boot-guardian (proposed)",
		Summary: "Unattended reboot recovery: FileVault pre-boot unlock, autologin, Tailscale-at-boot, dead-man if it doesn't rejoin."},
	{Name: "Backup Guardian", Kind: "actuator", Scope: "node", Status: PluginProposed,
		Tool: "backup-guardian", Repo: "eidos-agi/backup-guardian (proposed)",
		Summary: "Watches Time Machine + offsite freshness, kicks a run when stale, periodic test-restore."},
	{Name: "Secrets Analyst", Kind: "analyst", Scope: "node", Status: PluginProposed,
		Tool: "secrets-analyst", Repo: "eidos-agi/secrets-analyst (proposed)",
		Summary: "Credential hygiene: keys in dotfiles/git history, stale SSH, key age, 1Password/Keeper health."},
	{Name: "Intrusion Sentinel", Kind: "actuator", Scope: "node", Status: PluginProposed,
		Tool: "intrusion-sentinel", Repo: "eidos-agi/intrusion-sentinel (proposed)",
		Summary: "Real-time watch on new listening ports, launch items, and authorized_keys on the remote-accessible box."},
	{Name: "Update Guardian", Kind: "actuator", Scope: "node", Status: PluginProposed,
		Tool: "update-guardian", Repo: "eidos-agi/update-guardian (proposed)",
		Summary: "Staged macOS/brew/toolchain updates with pre-update snapshots so an auto-update never bricks boot."},
	{Name: "Restore Analyst", Kind: "analyst", Scope: "node", Status: PluginProposed,
		Tool: "restore-analyst", Repo: "eidos-agi/restore-analyst (proposed)",
		Summary: "Proves backups actually restore: coverage map, what's NOT backed up, restore-time estimates."},
	{Name: "Claude Frugality", Kind: "analyst", Scope: "node", Status: PluginProposed,
		Tool: "claude-frugality", Repo: "eidos-agi/claude-frugality (proposed)",
		Summary: "Derives Claude Code's cost drivers from session transcripts (subagent-heavy, >150k context, parallel sessions, expensive MCP) and surfaces how to spend limits cheaper."},
}
