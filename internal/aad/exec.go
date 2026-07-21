package aad

import (
	"context"
	"os/exec"
	"strings"
	"time"
)

// run executes a command with a 10s timeout and returns trimmed stdout.
// Returns "" on any error — checks treat missing tools as "no signal", matching
// the Python subprocess try/except idiom.
func run(name string, args ...string) string {
	return runT(10*time.Second, name, args...)
}

func runT(timeout time.Duration, name string, args ...string) string {
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()
	out, err := exec.CommandContext(ctx, name, args...).Output()
	if err != nil {
		return ""
	}
	return strings.TrimRight(string(out), "\n")
}
