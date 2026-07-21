package aad

import (
	"os"
	"path/filepath"
	"testing"
	"time"
)

func mkPoints(startFree float64, gbPerHour float64, n int, step time.Duration) []vitalsPoint {
	base := time.Date(2026, 7, 21, 10, 0, 0, 0, time.Local)
	pts := make([]vitalsPoint, n)
	for i := range pts {
		dt := time.Duration(i) * step
		pts[i] = vitalsPoint{T: base.Add(dt), FreeGB: startFree + gbPerHour*dt.Hours()}
	}
	return pts
}

func TestFillRate(t *testing.T) {
	// Falling 1.5 GB/h, sampled every 5 min for 2h → rate ≈ -1.5.
	pts := mkPoints(60, -1.5, 25, 5*time.Minute)
	r, used, ok := fillRateGBPerHour(pts, 2*time.Hour)
	if !ok || used < 20 || r > -1.4 || r < -1.6 {
		t.Errorf("falling series: got rate=%v used=%d ok=%v want ≈-1.5", r, used, ok)
	}

	// Flat series → rate ≈ 0.
	if r, _, ok := fillRateGBPerHour(mkPoints(60, 0, 10, 5*time.Minute), 2*time.Hour); !ok || r < -0.01 || r > 0.01 {
		t.Errorf("flat series: got %v want ~0", r)
	}

	// One point → not ok (tell user to keep monitor running).
	if _, _, ok := fillRateGBPerHour(mkPoints(60, 0, 1, time.Minute), 2*time.Hour); ok {
		t.Error("single point must not produce a rate")
	}

	// Window excludes old points: 24h of data, rate over last 2h only.
	old := mkPoints(100, 0, 12, time.Hour)         // flat day
	recent := mkPoints(100, -2, 24, 5*time.Minute) // then -2/h
	for i := range recent {                        // shift after old
		recent[i].T = old[len(old)-1].T.Add(time.Duration(i+1) * 5 * time.Minute)
	}
	r, _, ok = fillRateGBPerHour(append(old, recent...), 2*time.Hour)
	if !ok || r > -1.8 || r < -2.2 {
		t.Errorf("windowed rate: got %v want ≈-2", r)
	}
}

func TestGrowersBetween(t *testing.T) {
	prev := hotspotSnapshot{Sizes: map[string]float64{"docker-vm-disk": 40, "xdg-cache": 19, "trash": 1}}
	cur := hotspotSnapshot{Sizes: map[string]float64{"docker-vm-disk": 44, "xdg-cache": 19, "trash": 0.5, "new-item": 9}}
	g := growersBetween(prev, cur)
	if len(g) != 1 || g[0].Item != "docker-vm-disk" || g[0].DeltaGB != 4 || g[0].NowGB != 44 {
		t.Errorf("growers: got %+v want [docker-vm-disk +4 → 44]", g)
	}
}

func TestReadVitalsFree(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "vitals.ndjson")
	os.WriteFile(path, []byte(
		`{"ts":"2026-07-21T10:00:00","load":[1,1,1],"swap_mb":100}`+"\n"+ // old sample, no free_gb → skipped
			`{"ts":"2026-07-21T10:01:00","free_gb":60.5,"disk_used_pct":93.5}`+"\n"+
			"garbage line\n"+
			`{"ts":"2026-07-21T10:02:00","free_gb":60.4}`+"\n"), 0o644)
	pts := readVitalsFree(path, 1<<20)
	if len(pts) != 2 || pts[0].FreeGB != 60.5 || pts[1].FreeGB != 60.4 {
		t.Errorf("got %+v want 2 points 60.5/60.4", pts)
	}
}
