package aad

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"time"
)

// Reclaim plan — read-only ranked disk-reclaim candidates for agents.
// aad never deletes anything: every item carries the command a HUMAN must
// approve before an agent runs it. Sizes come from real probes (du, stat,
// tmutil), rules from ~/.config/eidos/storage-tiers.json.

// ReclaimItem is one reclaim candidate. EstGB < 0 means "probe failed/absent".
type ReclaimItem struct {
	Item           string  `json:"item"`
	Path           string  `json:"path,omitempty"`
	EstGB          float64 `json:"est_gb"`
	Risk           string  `json:"risk"`
	ApprovalNeeded bool    `json:"approval_needed"`
	Command        string  `json:"command"`
	Details        string  `json:"details,omitempty"`
}

// ReclaimPlan is the full agent-facing plan.
type ReclaimPlan struct {
	FreeGB     float64       `json:"free_gb"`
	MinFreeGB  float64       `json:"min_free_gb"`
	BelowFloor bool          `json:"below_floor"`
	Items      []ReclaimItem `json:"items"`
	Rules      []string      `json:"rules"`
	Note       string        `json:"note"`
}

// storageTiers is the subset of ~/.config/eidos/storage-tiers.json aad needs.
type storageTiers struct {
	Tiers []struct {
		ID        string  `json:"id"`
		Path      string  `json:"path"`
		MinFreeGB float64 `json:"min_free_gb"`
	} `json:"tiers"`
	Rules []string `json:"rules"`
}

// loadStorageTiers reads the tier config. Missing/broken file → defaults
// (min_free 50, no rules) so the plan still renders on unconfigured machines.
func loadStorageTiers(path string) (minFreeGB float64, rules []string) {
	minFreeGB = 50
	raw, err := os.ReadFile(path)
	if err != nil {
		return minFreeGB, nil
	}
	var st storageTiers
	if json.Unmarshal(raw, &st) != nil {
		return minFreeGB, nil
	}
	for _, t := range st.Tiers {
		if t.ID == "hot" && t.MinFreeGB > 0 {
			minFreeGB = t.MinFreeGB
		}
	}
	return minFreeGB, st.Rules
}

func defaultTiersPath() string {
	home, _ := os.UserHomeDir()
	return filepath.Join(home, ".config", "eidos", "storage-tiers.json")
}

// duGB returns the on-disk size of path in decimal GB, or -1 on failure.
// Works for sparse files too (du counts allocated blocks — what matters for
// Docker.raw). 60s cap: cache trees on a 94%-full disk are slow to walk.
func duGB(path string) float64 {
	out := runT(60*time.Second, "du", "-sk", path)
	fields := strings.Fields(out)
	if len(fields) == 0 {
		return -1
	}
	k, err := strconv.ParseFloat(fields[0], 64)
	if err != nil {
		return -1
	}
	return k * 1024 / 1e9
}

// BuildReclaimPlan probes the standard reclaim buckets. Every path probe is
// independent and failure-tolerant; items with est_gb=-1 exist but unsized.
func BuildReclaimPlan() ReclaimPlan {
	home, _ := os.UserHomeDir()
	minFree, rules := loadStorageTiers(defaultTiersPath())

	freeGB := -1.0
	if _, free := diskUsage(); free > 0 {
		freeGB = float64(free) / 1e9
	}

	// Disjoint paths only — no double counting (~/.cache listed whole, its
	// subdirs called out in the command text instead of as separate rows).
	candidates := []ReclaimItem{
		{
			Item: "docker-vm-disk", Path: filepath.Join(home, "Library/Containers/com.docker.docker/Data/vms/0/data/Docker.raw"),
			Risk: "medium — volumes may hold live data; review before prune", ApprovalNeeded: true,
			Command: "docker system df -v  # review; then: docker system prune, remove unused volumes, shrink disk in Docker Desktop settings",
		},
		{
			Item: "user-caches", Path: filepath.Join(home, "Library/Caches"),
			Risk: "low — rebuildable", ApprovalNeeded: true,
			Command: "du -sh ~/Library/Caches/* | sort -rh | head  # review, then rm -rf selected subdirs",
		},
		{
			Item: "xdg-cache", Path: filepath.Join(home, ".cache"),
			Risk: "low — rebuildable (huggingface/uv/whisper.cpp re-download on demand)", ApprovalNeeded: true,
			Command: "du -sh ~/.cache/* | sort -rh | head  # huggingface + uv are the usual bulk",
		},
		{
			Item: "ollama-models", Path: filepath.Join(home, ".ollama"),
			Risk: "medium — re-pullable, but check EidosModels offload policy first", ApprovalNeeded: true,
			Command: "ollama list  # rm unused models, or offload to mac-mini-01:/Volumes/EidosModels (ML weights only)",
		},
		{
			Item: "claude-session-transcripts", Path: filepath.Join(home, ".claude/projects"),
			Risk: "medium-high — old session resume history; archive, don't delete", ApprovalNeeded: true,
			Command: "archive sessions >30d to mac-mini-01 cold tier before removal",
		},
		{
			Item: "codex-worktrees-sessions", Path: filepath.Join(home, ".codex"),
			Risk: "medium — stale worktrees may hold uncommitted work; inspect first", ApprovalNeeded: true,
			Command: "du -sh ~/.codex/* | sort -rh | head  # prune stale worktrees/sessions after review",
		},
		{
			Item: "ios-simulators", Path: filepath.Join(home, "Library/Developer/CoreSimulator"),
			Risk: "low — recreatable", ApprovalNeeded: true,
			Command: "xcrun simctl delete unavailable",
		},
		{
			Item: "trash", Path: filepath.Join(home, ".Trash"),
			Risk: "low — already discarded", ApprovalNeeded: true,
			Command: "empty Trash from Finder",
		},
	}

	items := candidates[:0]
	for _, c := range candidates {
		if _, err := os.Stat(c.Path); err != nil {
			continue
		}
		c.EstGB = round1(duGB(c.Path))
		// The allocated-vs-active delta is the real Docker reclaim signal:
		// a 44 GB Docker.raw holding 9 GB of live data means ~35 GB back
		// from prune + shrink, not 44.
		if c.Item == "docker-vm-disk" && c.EstGB > 0 {
			if used := dockerActiveGB(); used >= 0 {
				c.Details = fmt.Sprintf("%.1f GB allocated, %.1f GB held by docker data (images+containers+volumes) — only ~%.0f GB is VM slack; bigger reclaim means deleting volumes/images after review", c.EstGB, used, c.EstGB-used)
			}
		}
		items = append(items, c)
	}

	if snap := snapshotItem(); snap != nil {
		items = append(items, *snap)
	}

	// Largest first; unsized (-1) last.
	sort.SliceStable(items, func(i, j int) bool { return items[i].EstGB > items[j].EstGB })

	return ReclaimPlan{
		FreeGB:     round1(freeGB),
		MinFreeGB:  minFree,
		BelowFloor: freeGB >= 0 && freeGB < minFree,
		Items:      items,
		Rules:      rules,
		Note:       "aad is diagnose-only. Every command here requires human approval before an agent runs it. Work docs are never reclaim candidates.",
	}
}

// snapshotItem reports Time Machine local snapshots. OS-update snapshots
// (com.apple.os.update-*) are managed by macOS and rarely thin — the command
// reflects that so agents stop cargo-culting thinlocalsnapshots.
func snapshotItem() *ReclaimItem {
	out := run("tmutil", "listlocalsnapshots", "/")
	if out == "" {
		return nil
	}
	var names []string
	for _, line := range strings.Split(out, "\n") {
		line = strings.TrimSpace(line)
		if line != "" && !strings.HasPrefix(line, "Snapshots for") {
			names = append(names, line)
		}
	}
	if len(names) == 0 {
		return nil
	}
	osUpdateOnly := true
	for _, n := range names {
		if !strings.HasPrefix(n, "com.apple.os.update-") {
			osUpdateOnly = false
			break
		}
	}
	cmd := "sudo tmutil thinlocalsnapshots / 9999999999 1  # measure df before/after"
	risk := "low — snapshots regenerate"
	if osUpdateOnly {
		cmd = "only com.apple.os.update-* snapshots present — thinning rarely reclaims these; measure df before/after: sudo tmutil thinlocalsnapshots / 9999999999 1"
		risk = "low — but likely reclaims little (OS-update snapshots only)"
	}
	return &ReclaimItem{
		Item: "tm-local-snapshots", EstGB: -1,
		Risk: risk, ApprovalNeeded: true, Command: cmd,
	}
}

// dockerActiveGB sums docker's own view of image+container+volume usage
// (decimal GB), or -1 if docker is absent/hung. Compared against Docker.raw's
// allocated blocks it exposes how much a prune + shrink would return.
func dockerActiveGB() float64 {
	out := runT(30*time.Second, "docker", "system", "df", "--format", "{{.Size}}")
	if out == "" {
		return -1
	}
	total := 0.0
	for _, line := range strings.Split(out, "\n") {
		total += dockerVolumesParseSizeGB(line)
	}
	return round1(total)
}

// diskUsage returns (total, free) bytes for the boot container via diskutil,
// or zeros on failure. Shared with check_disk.
func diskUsage() (total, free int64) {
	out := run("diskutil", "info", "/")
	for _, line := range strings.Split(out, "\n") {
		if k, v, ok := strings.Cut(line, ":"); ok {
			switch strings.TrimSpace(k) {
			case "Disk Size":
				total = parseBytesField(strings.TrimSpace(v))
			case "Container Free Space":
				free = parseBytesField(strings.TrimSpace(v))
			}
		}
	}
	return total, free
}

func round1(v float64) float64 {
	if v < 0 {
		return v
	}
	return float64(int(v*10+0.5)) / 10
}

// RenderReclaimJSON is the CLI entrypoint payload.
func RenderReclaimJSON() string {
	b, _ := json.MarshalIndent(BuildReclaimPlan(), "", "  ")
	return string(b)
}
