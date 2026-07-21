package aad

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

// Disk fill-rate learning (findings/0013): answer "how fast is free space
// falling, and what path is growing?" from two ledgers the daemon already
// keeps warm — vitals.ndjson (free_gb per tick, written by the Python
// monitor) and disk-hotspots.ndjson (watched-path sizes, written here).
// Read-only like everything else: growth points at reclaim-plan, never deletes.

func hotspotsLogPath() string { return filepath.Join(logDir(), "disk-hotspots.ndjson") }

// vitalsPoint is one (time, free_gb) observation.
type vitalsPoint struct {
	T      time.Time
	FreeGB float64
}

// readVitalsFree parses free_gb points from the tail of vitals.ndjson.
// Old samples without free_gb are skipped — the field only exists since
// 2026-07-21, and old readers/writers stay compatible.
func readVitalsFree(path string, maxBytes int64) []vitalsPoint {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil
	}
	if int64(len(raw)) > maxBytes {
		raw = raw[int64(len(raw))-maxBytes:] // tail only — first line may be torn, the { guard skips it
	}
	var points []vitalsPoint
	for _, line := range strings.Split(string(raw), "\n") {
		line = strings.TrimSpace(line)
		if line == "" || !strings.HasPrefix(line, "{") {
			continue
		}
		var s struct {
			TS     string  `json:"ts"`
			FreeGB float64 `json:"free_gb"`
		}
		if json.Unmarshal([]byte(line), &s) != nil || s.FreeGB == 0 || s.TS == "" {
			continue
		}
		t, err := time.ParseInLocation("2006-01-02T15:04:05", s.TS, time.Local)
		if err != nil {
			continue
		}
		points = append(points, vitalsPoint{T: t, FreeGB: s.FreeGB})
	}
	return points
}

// fillRateGBPerHour fits a least-squares line over the points inside the
// window ending at the newest point. Negative = free space falling. ok=false
// with fewer than 2 points (rate needs a series — tell the user to leave the
// monitor running).
func fillRateGBPerHour(points []vitalsPoint, window time.Duration) (rate float64, used int, ok bool) {
	if len(points) < 2 {
		return 0, len(points), false
	}
	cutoff := points[len(points)-1].T.Add(-window)
	var xs, ys []float64
	for _, p := range points {
		if p.T.Before(cutoff) {
			continue
		}
		xs = append(xs, p.T.Sub(cutoff).Hours())
		ys = append(ys, p.FreeGB)
	}
	if len(xs) < 2 {
		return 0, len(xs), false
	}
	n := float64(len(xs))
	var sx, sy, sxy, sxx float64
	for i := range xs {
		sx += xs[i]
		sy += ys[i]
		sxy += xs[i] * ys[i]
		sxx += xs[i] * xs[i]
	}
	denom := n*sxx - sx*sx
	if denom == 0 {
		return 0, len(xs), false
	}
	return (n*sxy - sx*sy) / denom, len(xs), true
}

// hotspotSnapshot is one sizes-by-item observation in the ledger.
type hotspotSnapshot struct {
	TS    string             `json:"ts"`
	Sizes map[string]float64 `json:"sizes"`
}

// SampleHotspots measures the watched reclaim paths (capped du, never
// full-home) and appends a snapshot line to disk-hotspots.ndjson.
func SampleHotspots() (hotspotSnapshot, error) {
	home, _ := os.UserHomeDir()
	snap := hotspotSnapshot{TS: time.Now().Format("2006-01-02T15:04:05"), Sizes: map[string]float64{}}
	for _, c := range reclaimCandidates(home) {
		if _, err := os.Stat(c.Path); err != nil {
			continue
		}
		if gb := duGB(c.Path); gb >= 0 {
			snap.Sizes[c.Item] = round1(gb)
		}
	}
	if err := os.MkdirAll(logDir(), 0o755); err != nil {
		return snap, err
	}
	f, err := os.OpenFile(hotspotsLogPath(), os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
	if err != nil {
		return snap, err
	}
	defer f.Close()
	b, _ := json.Marshal(snap)
	_, err = f.Write(append(b, '\n'))
	return snap, err
}

func readHotspots(path string) []hotspotSnapshot {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil
	}
	var snaps []hotspotSnapshot
	for _, line := range strings.Split(string(raw), "\n") {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		var s hotspotSnapshot
		if json.Unmarshal([]byte(line), &s) == nil && len(s.Sizes) > 0 {
			snaps = append(snaps, s)
		}
	}
	return snaps
}

// Grower is a watched path that got bigger between two snapshots.
type Grower struct {
	Item    string  `json:"item"`
	DeltaGB float64 `json:"delta_gb"`
	NowGB   float64 `json:"now_gb"`
}

// growers diffs the oldest-vs-newest snapshot pair, positive deltas only,
// biggest first.
func growersBetween(prev, cur hotspotSnapshot) []Grower {
	var out []Grower
	for item, now := range cur.Sizes {
		before, seen := prev.Sizes[item]
		if !seen {
			continue
		}
		if d := round1(now - before); d > 0 {
			out = append(out, Grower{Item: item, DeltaGB: d, NowGB: now})
		}
	}
	sort.Slice(out, func(i, j int) bool { return out[i].DeltaGB > out[j].DeltaGB })
	return out
}

// GrowthReport is the `aad growth --json` payload.
type GrowthReport struct {
	FreeGB          float64  `json:"free_gb"`
	MinFreeGB       float64  `json:"min_free_gb"`
	RateGBPerHour   *float64 `json:"rate_gb_per_hour"`   // 2h window; null = not enough samples
	RateGBPerDay    *float64 `json:"rate_gb_per_day"`    // 24h window; null = not enough samples
	ETAHoursToFloor *float64 `json:"eta_hours_to_floor"` // null unless free is falling
	SamplesUsed     int      `json:"samples_used"`
	Growers         []Grower `json:"growers"`
	Note            string   `json:"note"`
}

// BuildGrowthReport computes rate/ETA from the vitals series and growers from
// the hotspot ledger. Pure aside from file reads — testable via the helpers.
func BuildGrowthReport() GrowthReport {
	minFree, _ := loadStorageTiers(defaultTiersPath())
	rep := GrowthReport{MinFreeGB: minFree}

	points := readVitalsFree(filepath.Join(logDir(), "vitals.ndjson"), 512*1024)
	if len(points) > 0 {
		rep.FreeGB = points[len(points)-1].FreeGB
	} else if _, free := diskUsage(); free > 0 {
		rep.FreeGB = round1(float64(free) / 1e9)
	}

	if r, used, ok := fillRateGBPerHour(points, 2*time.Hour); ok {
		v := round1(r*100) / 100
		rep.RateGBPerHour = &v
		rep.SamplesUsed = used
		if r < 0 && rep.FreeGB > minFree {
			eta := round1((rep.FreeGB - minFree) / -r)
			rep.ETAHoursToFloor = &eta
		}
	}
	if r, _, ok := fillRateGBPerHour(points, 24*time.Hour); ok {
		v := round1(r * 24)
		rep.RateGBPerDay = &v
	}

	snaps := readHotspots(hotspotsLogPath())
	if len(snaps) >= 2 {
		rep.Growers = growersBetween(snaps[0], snaps[len(snaps)-1])
	}

	switch {
	case rep.RateGBPerHour == nil:
		rep.Note = "Not enough free_gb samples yet — leave `aad serve` / the vitals monitor running for an hour, then re-run. Use `aad growth --sample` now and again later to seed the hotspot ledger."
	case len(snaps) < 2:
		rep.Note = "Rate computed from vitals; growers need two hotspot snapshots — run `aad growth --sample` now and again in an hour."
	default:
		rep.Note = "Read-only. If free is falling, run `aad reclaim-plan --json` and get human approval before any delete."
	}
	return rep
}

// RenderGrowthJSON is the CLI entrypoint payload.
func RenderGrowthJSON() string {
	b, _ := json.MarshalIndent(BuildGrowthReport(), "", "  ")
	return string(b)
}

// growthDiskFinding gives disk_health its forward-looking pointer: if free is
// falling fast or the floor is near in time, say so. Cheap (tail read only).
func growthDiskFinding(freeGB, minFree float64) string {
	points := readVitalsFree(filepath.Join(logDir(), "vitals.ndjson"), 256*1024)
	r, _, ok := fillRateGBPerHour(points, 2*time.Hour)
	if !ok || r >= -0.5 {
		return ""
	}
	etaTxt := ""
	if freeGB > minFree {
		etaTxt = fmt.Sprintf(" — ~%.0fh until the %.0f GB floor", (freeGB-minFree)/-r, minFree)
	}
	return fmt.Sprintf("Free space falling %.1f GB/h%s. Run `aad growth --json` to see what's growing.", -r, etaTxt)
}
