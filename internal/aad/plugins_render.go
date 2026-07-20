package aad

import (
	"encoding/json"
	"fmt"
	"strings"
)

// RenderPlugins lists the plugin catalog: active (with a live health probe) and
// proposed (the ranked roadmap).
func RenderPlugins() string {
	var b strings.Builder
	b.WriteString("\naad plugins — external tools aad wraps (read-only)\n")

	all := Plugins()
	writeGroup := func(title string, status PluginStatus, probe bool) {
		fmt.Fprintf(&b, "\n%s\n", title)
		for _, p := range all {
			if p.Status != status {
				continue
			}
			mark := "·"
			detail := p.Repo
			if probe && p.Health != nil {
				if ok, d := p.Health(); ok {
					mark, detail = "✓", d
				} else {
					mark, detail = "✗", d
				}
			}
			fmt.Fprintf(&b, "  %s  %-18s %-9s %-5s %s\n", mark, p.Name, p.Kind, p.Scope, p.Summary)
			fmt.Fprintf(&b, "        %s — %s\n", p.Tool, detail)
		}
	}

	writeGroup("ACTIVE", PluginActive, true)
	writeGroup("PROPOSED (ranked)", PluginProposed, false)
	return b.String()
}

// RenderPluginsJSON emits the catalog as JSON, probing active plugins' health.
func RenderPluginsJSON() string {
	type jp struct {
		Name       string `json:"name"`
		Kind       string `json:"kind"`
		Scope      string `json:"scope"`
		Status     string `json:"status"`
		Tool       string `json:"tool"`
		Repo       string `json:"repo"`
		Summary    string `json:"summary"`
		HealthOK   *bool  `json:"health_ok,omitempty"`
		HealthNote string `json:"health_note,omitempty"`
	}
	all := Plugins()
	out := make([]jp, 0, len(all))
	for _, p := range all {
		row := jp{p.Name, p.Kind, p.Scope, string(p.Status), p.Tool, p.Repo, p.Summary, nil, ""}
		if p.Health != nil {
			ok, note := p.Health()
			row.HealthOK, row.HealthNote = &ok, note
		}
		out = append(out, row)
	}
	buf, _ := json.MarshalIndent(out, "", "  ")
	return string(buf)
}
