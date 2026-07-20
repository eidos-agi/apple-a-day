package aad

import "testing"

func TestSpaceHogFindings(t *testing.T) {
	rep := spaceHogReport{
		TotalReclaimableBytes: 12_000_000_000,
		Sections: []spaceHogSection{
			{Name: "trash", TotalBytes: 0, Items: nil},
			{Name: "caches", TotalBytes: 10_000_000_000, Items: []spaceHogItem{{Bytes: 6e9, Label: "Chrome cache"}}},
			{Name: "downloads_old", TotalBytes: 2_000_000_000, Items: []spaceHogItem{{Bytes: 2e9, Label: "big.dmg"}}},
		},
	}
	fs := spaceHogFindings(rep)

	// headline + 2 non-empty sections (trash with 0 bytes is skipped)
	if len(fs) != 3 {
		t.Fatalf("got %d findings, want 3 (headline + caches + downloads_old)", len(fs))
	}
	if fs[0].Severity != INFO {
		t.Errorf("headline severity: got %v want INFO", fs[0].Severity)
	}
	// sections sorted largest-first → caches before downloads_old
	if fs[1].Summary[:6] != "caches" {
		t.Errorf("expected caches first, got %q", fs[1].Summary)
	}
}
