package aad

import (
	"encoding/json"
	"log"
	"net/http"
	"sync"
	"time"
)

// `aad serve`: a long-lived daemon that caches the last full checkup and serves
// it over localhost HTTP, so clients (the SwiftUI menu bar, conduit) read the
// cached result instead of spawning a fresh scan every refresh. Mirrors
// resource-sentinel's :9341 status API — aad becomes a proper fleet daemon.

type server struct {
	mu      sync.RWMutex
	report  CheckupReport
	updated time.Time
}

func (s *server) refresh() {
	rep := RunCheckup(true, nil) // default checks only — no slow opt-in scans
	s.mu.Lock()
	s.report = rep
	s.updated = time.Now()
	s.mu.Unlock()
	LogCheckup(rep, "serve")
}

func (s *server) snapshot() (CheckupReport, time.Time) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.report, s.updated
}

// RunServer listens immediately and refreshes the cached checkup in the
// background (initial warm + every interval). Endpoints that need data return
// 503 until the first checkup lands. Blocks until ListenAndServe returns.
func RunServer(addr string, interval time.Duration) error {
	s := &server{}
	go func() {
		s.refresh() // initial warm
		t := time.NewTicker(interval)
		defer t.Stop()
		for range t.C {
			s.refresh()
		}
	}()
	// Hourly hotspot snapshot feeds `aad growth` path attribution — capped du
	// over the watched reclaim paths, never a full-home scan.
	go func() {
		SampleHotspots()
		t := time.NewTicker(time.Hour)
		defer t.Stop()
		for range t.C {
			SampleHotspots()
		}
	}()

	// warmed serves the cached report as JSON via f, or 503 if not ready yet.
	warmed := func(f func(CheckupReport) string) http.HandlerFunc {
		return func(w http.ResponseWriter, r *http.Request) {
			rep, updated := s.snapshot()
			if updated.IsZero() {
				http.Error(w, `{"status":"warming"}`, http.StatusServiceUnavailable)
				return
			}
			writeJSON(w, f(rep))
		}
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte("ok\n"))
	})
	mux.HandleFunc("/version", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, VersionJSON())
	})
	mux.HandleFunc("/plugins", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, RenderPluginsJSON())
	})
	mux.HandleFunc("/score", warmed(ScoreJSONFromReport))
	mux.HandleFunc("/checkup", warmed(RenderJSON))
	mux.HandleFunc("/findings", warmed(func(rep CheckupReport) string {
		b, _ := json.MarshalIndent(buildLogEntry(rep, "serve"), "", "  ")
		return string(b)
	}))
	// Log each request so clients (menu bar, conduit) are observable.
	logged := func(h http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			log.Printf("%s %s from %s", r.Method, r.URL.Path, r.RemoteAddr)
			h.ServeHTTP(w, r)
		})
	}
	return http.ListenAndServe(addr, logged(mux))
}

func writeJSON(w http.ResponseWriter, body string) {
	w.Header().Set("Content-Type", "application/json")
	w.Write([]byte(body))
}
