package aad

import (
	"fmt"
	"sort"
	"strconv"
	"strings"
	"time"
)

func init() {
	register(Check{Name: "Docker Volumes", Run: checkDockerVolumes, OptIn: true})
}

// dockerVolumesEntry mirrors the Python (name, gb, links) tuple for a volume row.
type dockerVolumesEntry struct {
	name  string
	gb    float64
	links int
}

func checkDockerVolumes() CheckResult {
	r := CheckResult{Name: "Docker Volumes"}

	// docker may be absent — run() returns "" and we treat that as "not installed".
	if run("which", "docker") == "" {
		r.add(Finding{Check: "docker_volumes", Severity: INFO, Summary: "Docker not installed or not on PATH"})
		return r
	}

	var largeVolumes []dockerVolumesEntry
	var exitedContainers []string

	dfOut := runT(30*time.Second, "docker", "system", "df", "-v")
	if dfOut == "" {
		r.add(Finding{Check: "docker_volumes", Severity: INFO, Summary: "Docker daemon not running or not accessible"})
		return r
	}

	inVolumes := false
	for _, line := range strings.Split(dfOut, "\n") {
		if strings.HasPrefix(line, "VOLUME NAME") {
			inVolumes = true
			continue
		}
		if !inVolumes {
			continue
		}
		if strings.TrimSpace(line) == "" || strings.HasPrefix(line, "Build cache") {
			break
		}
		parts := strings.Fields(line)
		if len(parts) >= 3 {
			name := parts[0]
			links, err := strconv.Atoi(parts[1])
			if err != nil {
				links = 0
			}
			gb := dockerVolumesParseSizeGB(parts[2])
			if gb >= 5 {
				largeVolumes = append(largeVolumes, dockerVolumesEntry{name: name, gb: gb, links: links})
			}
		}
	}

	psOut := runT(15*time.Second, "docker", "ps", "-a", "--filter", "status=exited", "--format", "{{.Names}}\t{{.Size}}")
	for _, line := range strings.Split(strings.TrimSpace(psOut), "\n") {
		if strings.TrimSpace(line) != "" {
			exitedContainers = append(exitedContainers, strings.TrimSpace(line))
		}
	}

	if len(largeVolumes) > 0 {
		sort.Slice(largeVolumes, func(i, j int) bool { return largeVolumes[i].gb > largeVolumes[j].gb })

		var details strings.Builder
		for i, v := range largeVolumes {
			if i >= 8 {
				break
			}
			fmt.Fprintf(&details, "  %-40s %6.1f GB  links=%d\n", v.name, v.gb, v.links)
		}

		var orphans []string
		for _, v := range largeVolumes {
			if v.links == 0 {
				orphans = append(orphans, v.name)
			}
		}

		sev := WARNING
		for _, v := range largeVolumes {
			if v.gb > 20 {
				sev = CRITICAL
				break
			}
		}

		fix := storageGuardrail() +
			" `docker system df -v` before prune — export inactive volumes to cold tier if needed."
		if len(orphans) > 0 {
			n := len(orphans)
			if n > 3 {
				n = 3
			}
			fix += fmt.Sprintf(" Orphan volumes (0 links): %s — export to MacMiniStorage before prune.", strings.Join(orphans[:n], ", "))
		}

		r.add(Finding{
			Check:    "docker_volumes",
			Severity: sev,
			Summary:  fmt.Sprintf("%d Docker volume(s) ≥5 GB (largest: %.1f GB)", len(largeVolumes), largeVolumes[0].gb),
			Details:  strings.TrimRight(details.String(), "\n"),
			Fix:      fix,
		})
	}

	if len(exitedContainers) > 2 {
		var details strings.Builder
		for i, c := range exitedContainers {
			if i >= 6 {
				break
			}
			fmt.Fprintf(&details, "  %s\n", c)
		}
		r.add(Finding{
			Check:    "docker_volumes",
			Severity: INFO,
			Summary:  fmt.Sprintf("%d exited containers still on disk", len(exitedContainers)),
			Details:  strings.TrimRight(details.String(), "\n"),
			Fix:      "`docker container prune` after confirming containers are not needed.",
		})
	}

	if len(r.Findings) == 0 {
		r.add(Finding{Check: "docker_volumes", Severity: OK, Summary: "No large Docker volumes detected"})
	}

	return r
}

// dockerVolumesParseSizeGB parses Docker size strings like 31.42GB, 1.795GB, 49.09MB.
func dockerVolumesParseSizeGB(sizeStr string) float64 {
	sizeStr = strings.TrimSpace(sizeStr)
	switch {
	case strings.HasSuffix(sizeStr, "GB"):
		v, _ := strconv.ParseFloat(strings.TrimSuffix(sizeStr, "GB"), 64)
		return v
	case strings.HasSuffix(sizeStr, "MB"):
		v, _ := strconv.ParseFloat(strings.TrimSuffix(sizeStr, "MB"), 64)
		return v / 1024
	case strings.HasSuffix(sizeStr, "KB"):
		v, _ := strconv.ParseFloat(strings.TrimSuffix(sizeStr, "KB"), 64)
		return v / (1024 * 1024)
	}
	return 0.0
}
