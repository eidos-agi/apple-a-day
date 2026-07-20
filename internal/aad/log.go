package aad

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"time"
)

// Checkup logging + score output — schemas match the SwiftUI menu-bar app's
// Codable models (app/AppleADay/Sources/Models.swift): CheckupLogEntry (the
// checkup.ndjson stream) and ScoreOutput (`aad score --json`). Keep field names
// and shapes in lockstep with that file, or the menu bar goes blank.

func logDir() string {
	home, _ := os.UserHomeDir()
	return filepath.Join(home, ".config", "eidos", "aad-logs")
}

func checkupLogPath() string { return filepath.Join(logDir(), "checkup.ndjson") }

// checkupLogEntry mirrors Swift CheckupLogEntry.
type checkupLogEntry struct {
	TS         string         `json:"ts"`
	Trigger    string         `json:"trigger"`
	DurationMS int64          `json:"duration_ms"`
	Score      int            `json:"score"`
	Grade      string         `json:"grade"`
	Matrix     map[string]int `json:"matrix"`
	Counts     severityCounts `json:"counts"`
	Criticals  []string       `json:"criticals"`
	Warnings   []string       `json:"warnings"`
}

type severityCounts struct {
	Critical int `json:"critical"`
	Warning  int `json:"warning"`
	Info     int `json:"info"`
	OK       int `json:"ok"`
}

// scoreOutput mirrors Swift ScoreOutput (`aad score --json`).
type scoreOutput struct {
	TS     string         `json:"ts"`
	Score  int            `json:"score"`
	Grade  string         `json:"grade"`
	Matrix map[string]int `json:"matrix"`
}

func buildLogEntry(rep CheckupReport, trigger string) checkupLogEntry {
	sc := ComputeScore(rep.Results)
	var counts severityCounts
	var crit, warn []string
	for _, r := range rep.Results {
		for _, f := range r.Findings {
			switch f.Severity {
			case CRITICAL:
				counts.Critical++
				crit = append(crit, f.Summary)
			case WARNING:
				counts.Warning++
				warn = append(warn, f.Summary)
			case INFO:
				counts.Info++
			case OK:
				counts.OK++
			}
		}
	}
	return checkupLogEntry{
		TS: time.Now().Format(time.RFC3339), Trigger: trigger,
		DurationMS: rep.DurationMS, Score: sc.Score, Grade: sc.Grade, Matrix: sc.Matrix,
		Counts: counts, Criticals: crit, Warnings: warn,
	}
}

// LogCheckup appends a checkup entry to checkup.ndjson (best-effort — the menu
// bar reads it; a checkup must not fail because logging couldn't write).
func LogCheckup(rep CheckupReport, trigger string) {
	if err := os.MkdirAll(logDir(), 0o755); err != nil {
		return
	}
	line, err := json.Marshal(buildLogEntry(rep, trigger))
	if err != nil {
		return
	}
	f, err := os.OpenFile(checkupLogPath(), os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
	if err != nil {
		return
	}
	defer f.Close()
	f.Write(append(line, '\n'))
}

// LatestScoreJSON returns the ScoreOutput JSON from the most recent logged
// checkup, or "" if there is no log yet (caller should run a checkup first).
func LatestScoreJSON() string {
	data, err := os.ReadFile(checkupLogPath())
	if err != nil {
		return ""
	}
	lines := strings.Split(strings.TrimRight(string(data), "\n"), "\n")
	last := lines[len(lines)-1]
	if strings.TrimSpace(last) == "" {
		return ""
	}
	var e checkupLogEntry
	if json.Unmarshal([]byte(last), &e) != nil {
		return ""
	}
	buf, _ := json.MarshalIndent(scoreOutput{TS: e.TS, Score: e.Score, Grade: e.Grade, Matrix: e.Matrix}, "", "  ")
	return string(buf)
}

// ScoreJSONFromReport builds ScoreOutput directly from a fresh report.
func ScoreJSONFromReport(rep CheckupReport) string {
	sc := ComputeScore(rep.Results)
	buf, _ := json.MarshalIndent(scoreOutput{
		TS: time.Now().Format(time.RFC3339), Score: sc.Score, Grade: sc.Grade, Matrix: sc.Matrix,
	}, "", "  ")
	return string(buf)
}
