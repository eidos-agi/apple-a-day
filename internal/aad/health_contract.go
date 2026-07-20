package aad

import (
	"encoding/json"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"time"
)

// The health contract: any Eidos program becomes aad-monitorable by dropping a
// manifest in ~/.config/eidos/health.d/<name>.json describing how to probe it.
// aad discovers every manifest and probes liveness + health UNIFORMLY — no
// per-tool Go. A new monitorable program is a manifest file, not a code change.
//
// Probes are REAL, never age-based: a live launchd PID, an accepted TCP
// connection, an ok=true health response. File mtime/staleness is a proxy that
// lies (a wedged process leaves a fresh heartbeat; a healthy idle one leaves a
// stale file), so it is never used to decide active/healthy.

// Manifest is one program's health-contract declaration.
type Manifest struct {
	Name     string       `json:"name"`
	Kind     string       `json:"kind"`  // actuator | analyst
	Scope    string       `json:"scope"` // node | fleet
	Repo     string       `json:"repo"`
	Summary  string       `json:"summary"`
	Liveness LivenessSpec `json:"liveness"`
	Health   HealthSpec   `json:"health"`
}

// LivenessSpec: "is it running?" — exactly one of these should be set.
type LivenessSpec struct {
	Launchd string `json:"launchd,omitempty"` // launchd label; running == has a live PID
	Port    int    `json:"port,omitempty"`    // TCP port; running == connection accepted
	PIDFile string `json:"pidfile,omitempty"` // file holding a PID; running == signal 0 succeeds
}

// HealthSpec: "is it ok?" — exactly one of these should be set.
type HealthSpec struct {
	URL     string `json:"url,omitempty"`     // GET; ok == 200 (and {"ok":false} not present)
	Command string `json:"command,omitempty"` // shell cmd; ok == exit 0 (and {"ok":false} not present)
}

func healthContractDir() string {
	home, _ := os.UserHomeDir()
	return filepath.Join(home, ".config", "eidos", "health.d")
}

// DiscoverManifests reads every *.json in the health.d dir. Bad files are
// skipped (a malformed manifest must not break discovery of the others).
func DiscoverManifests() []Manifest {
	entries, err := os.ReadDir(healthContractDir())
	if err != nil {
		return nil
	}
	var out []Manifest
	for _, e := range entries {
		if e.IsDir() || !strings.HasSuffix(e.Name(), ".json") {
			continue
		}
		data, err := os.ReadFile(filepath.Join(healthContractDir(), e.Name()))
		if err != nil {
			continue
		}
		var m Manifest
		if json.Unmarshal(data, &m) == nil && m.Name != "" {
			out = append(out, m)
		}
	}
	return out
}

// HasLiveness reports whether a liveness probe is declared. CLI/analyst tools
// (space-hog) have no persistent process — they declare only health.
func (m Manifest) HasLiveness() bool {
	return m.Liveness.Launchd != "" || m.Liveness.Port != 0 || m.Liveness.PIDFile != ""
}

// ProbeLiveness answers "is it running?" via the declared mechanism. Real probe.
func (m Manifest) ProbeLiveness() (bool, string) {
	switch {
	case m.Liveness.Launchd != "":
		return launchdRunning(m.Liveness.Launchd)
	case m.Liveness.Port != 0:
		return portListening(m.Liveness.Port)
	case m.Liveness.PIDFile != "":
		return pidfileAlive(m.Liveness.PIDFile)
	}
	return false, "no liveness probe declared"
}

// ProbeHealth answers "is it ok?" via the declared mechanism. Real probe.
func (m Manifest) ProbeHealth() (bool, string) {
	switch {
	case m.Health.URL != "":
		return httpHealth(m.Health.URL)
	case m.Health.Command != "":
		return commandHealth(m.Health.Command)
	}
	// No health probe — fall back to liveness (running == as healthy as we know).
	return m.ProbeLiveness()
}

// launchdRunning: `launchctl list <label>` prints a dict with `"PID" = N;` only
// when the job has a live process. Loaded-but-not-running has no PID key.
func launchdRunning(label string) (bool, string) {
	out := run("launchctl", "list", label)
	if out == "" {
		return false, "not loaded"
	}
	for _, line := range strings.Split(out, "\n") {
		if strings.Contains(line, "\"PID\"") {
			return true, "running (" + strings.TrimSpace(line) + ")"
		}
	}
	return false, "loaded, not running"
}

func portListening(port int) (bool, string) {
	addr := net.JoinHostPort("127.0.0.1", strconv.Itoa(port))
	conn, err := net.DialTimeout("tcp", addr, 2*time.Second)
	if err != nil {
		return false, "not listening on " + addr
	}
	conn.Close()
	return true, "listening on " + addr
}

func pidfileAlive(path string) (bool, string) {
	data, err := os.ReadFile(path)
	if err != nil {
		return false, "no pidfile"
	}
	pid, err := strconv.Atoi(strings.TrimSpace(string(data)))
	if err != nil {
		return false, "bad pidfile"
	}
	// Signal 0 checks existence without affecting the process.
	if syscall.Kill(pid, 0) != nil {
		return false, "pid " + strconv.Itoa(pid) + " not alive"
	}
	return true, "pid " + strconv.Itoa(pid) + " alive"
}

// okField is the optional shared health shape: {"ok": bool, "detail": "..."}.
type okField struct {
	OK     *bool  `json:"ok"`
	Detail string `json:"detail"`
}

func httpHealth(url string) (bool, string) {
	c := http.Client{Timeout: 3 * time.Second}
	resp, err := c.Get(url)
	if err != nil {
		return false, "unreachable"
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		return false, "HTTP " + strconv.Itoa(resp.StatusCode)
	}
	// If the body carries {"ok":false}, honor it; otherwise 200 == ok.
	var f okField
	if json.NewDecoder(resp.Body).Decode(&f) == nil && f.OK != nil && !*f.OK {
		return false, detailOr(f.Detail, "reported not ok")
	}
	return true, "200 ok"
}

func commandHealth(command string) (bool, string) {
	out := run("/bin/sh", "-c", command)
	if out == "" {
		return false, "no output / nonzero exit"
	}
	var f okField
	if json.Unmarshal([]byte(out), &f) == nil && f.OK != nil {
		return *f.OK, detailOr(f.Detail, "reported")
	}
	return true, "ran ok"
}

func detailOr(detail, fallback string) string {
	if strings.TrimSpace(detail) != "" {
		return detail
	}
	return fallback
}
