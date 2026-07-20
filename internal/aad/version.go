package aad

import (
	"encoding/json"
	"runtime/debug"
)

// Version is the release string; override at build time with
// -ldflags "-X github.com/eidos-agi/apple-a-day/internal/aad.Version=v0.4.0".
var Version = "go-dev"

// BuildInfo returns (version, short commit, commit date). commit/date come from
// the VCS stamp Go embeds when building from the git repo — the honest proof of
// exactly which build is running.
func BuildInfo() (version, commit, date string) {
	version, commit, date = Version, "unknown", "unknown"
	info, ok := debug.ReadBuildInfo()
	if !ok {
		return
	}
	for _, s := range info.Settings {
		switch s.Key {
		case "vcs.revision":
			commit = s.Value
			if len(commit) > 12 {
				commit = commit[:12]
			}
		case "vcs.time":
			date = s.Value
		}
	}
	return
}

// VersionJSON is the /version payload and `aad version --json` output.
func VersionJSON() string {
	v, c, d := BuildInfo()
	buf, _ := json.MarshalIndent(map[string]string{
		"version": v, "commit": c, "date": d,
	}, "", "  ")
	return string(buf)
}
