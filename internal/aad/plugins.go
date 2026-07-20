package aad

import (
	"net/http"
	"time"
)

// Plugins in aad are not a runtime framework — Go compiles them in. A "plugin"
// is a check that wraps an external tool or daemon (its own repo/lifecycle),
// which aad surfaces read-only: resource-sentinel (the disk/resource actuator),
// space-hog (the deep space analyst), and — proposed — conduit (the fleet
// reachability brain) and the node guardians below. This file is the catalog +
// health probes; `aad plugins` renders it. Proposed entries are the roadmap and
// carry no Health probe until built.
// ponytail: a struct registry, not a loader/manifest system — 2 active + 7
// proposed plugins compiled into one binary don't need dynamic discovery.

type PluginStatus string

const (
	PluginActive   PluginStatus = "active"
	PluginProposed PluginStatus = "proposed"
)

// Plugin describes an external tool aad wraps (or plans to).
type Plugin struct {
	Name    string       // display name; matches the wrapping check's Name when active
	Kind    string       // "actuator" (acts in real time) | "analyst" (explains on demand)
	Scope   string       // "node" (this Mac) | "fleet" (all servers)
	Status  PluginStatus // active | proposed
	Tool    string       // external binary/daemon this wraps
	Repo    string       // where the tool lives
	Install string       // how to install it (active) or a one-line intent (proposed)
	Summary string       // why it exists
	// Health probes an active plugin's external tool; nil for proposed.
	Health func() (ok bool, detail string)
}

var plugins []Plugin

func registerPlugin(p Plugin) { plugins = append(plugins, p) }

// Plugins returns the catalog in registration (ranked) order.
func Plugins() []Plugin { return plugins }

func init() {
	// --- Active: the two that exist and are wired in ---
	registerPlugin(Plugin{
		Name: "Resource Sentinel", Kind: "actuator", Scope: "node", Status: PluginActive,
		Tool: "resource-sentinel", Repo: "eidos-agi/resource-sentinel",
		Install: "runs from ~/.local/bin via launchd (com.eidos.resource-sentinel)",
		Summary: "Real-time disk/RAM/CPU guardian: safe-cleans rebuildable caches, SIGSTOPs runaway writers.",
		Health: func() (bool, string) {
			c := http.Client{Timeout: 2 * time.Second}
			resp, err := c.Get(sentinelStatusURL)
			if err != nil {
				return false, "not responding on :9341"
			}
			resp.Body.Close()
			return true, "responding on :9341"
		},
	})
	registerPlugin(Plugin{
		Name: "Space Hogs", Kind: "analyst", Scope: "node", Status: PluginActive,
		Tool: "space-hog", Repo: "eidos-agi/space-hog",
		Install: "pipx install space-hog",
		Summary: "On-demand deep space audit: caches/Docker/Ollama/downloads reclaim taxonomy via `space-hog --json`.",
		Health: func() (bool, string) {
			if run("which", "space-hog") == "" {
				return false, "not on PATH"
			}
			return true, "installed"
		},
	})

	// --- Proposed: the ranked roadmap (does the same job at the next-riskiest
	// domain for a headless, always-on, fleet-critical Mac mini) ---
	registerPlugin(Plugin{
		Name: "Conduit", Kind: "actuator", Scope: "fleet", Status: PluginProposed,
		Tool: "conduit", Repo: "eidos-agi/conduit",
		Install: "aad manages the local conduit agent + pushes health into conduit proofs",
		Summary: "Fleet nervous system — ensures every server is online & accessible; aad reports up, conduit covers aad's own-death blind spot.",
	})
	registerPlugin(Plugin{
		Name: "Boot Guardian", Kind: "actuator", Scope: "node", Status: PluginProposed,
		Tool: "boot-guardian", Repo: "eidos-agi/boot-guardian (proposed)",
		Install: "proposed",
		Summary: "Unattended reboot recovery: FileVault pre-boot unlock, autologin, Tailscale-at-boot, dead-man if it doesn't rejoin.",
	})
	registerPlugin(Plugin{
		Name: "Backup Guardian", Kind: "actuator", Scope: "node", Status: PluginProposed,
		Tool: "backup-guardian", Repo: "eidos-agi/backup-guardian (proposed)",
		Install: "proposed",
		Summary: "Watches Time Machine + offsite freshness, kicks a run when stale, periodic test-restore.",
	})
	registerPlugin(Plugin{
		Name: "Secrets Analyst", Kind: "analyst", Scope: "node", Status: PluginProposed,
		Tool: "secrets-analyst", Repo: "eidos-agi/secrets-analyst (proposed)",
		Install: "proposed",
		Summary: "Credential hygiene: keys in dotfiles/git history, stale SSH, key age, 1Password/Keeper health.",
	})
	registerPlugin(Plugin{
		Name: "Intrusion Sentinel", Kind: "actuator", Scope: "node", Status: PluginProposed,
		Tool: "intrusion-sentinel", Repo: "eidos-agi/intrusion-sentinel (proposed)",
		Install: "proposed",
		Summary: "Real-time watch on new listening ports, launch items, and authorized_keys on the remote-accessible box.",
	})
	registerPlugin(Plugin{
		Name: "Update Guardian", Kind: "actuator", Scope: "node", Status: PluginProposed,
		Tool: "update-guardian", Repo: "eidos-agi/update-guardian (proposed)",
		Install: "proposed",
		Summary: "Staged macOS/brew/toolchain updates with pre-update snapshots so an auto-update never bricks boot.",
	})
	registerPlugin(Plugin{
		Name: "Restore Analyst", Kind: "analyst", Scope: "node", Status: PluginProposed,
		Tool: "restore-analyst", Repo: "eidos-agi/restore-analyst (proposed)",
		Install: "proposed",
		Summary: "Proves backups actually restore: coverage map, what's NOT backed up, restore-time estimates.",
	})
}
