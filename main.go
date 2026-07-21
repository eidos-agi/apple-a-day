// Command aad is the Go rewrite of apple-a-day — read-only macOS health checks.
package main

import (
	"flag"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/eidos-agi/apple-a-day/internal/aad"
)

func main() {
	if len(os.Args) < 2 {
		usage()
		os.Exit(2)
	}
	switch os.Args[1] {
	case "checkup":
		checkup(os.Args[2:])
	case "plugins":
		pluginsCmd(os.Args[2:])
	case "score":
		scoreCmd(os.Args[2:])
	case "reclaim-plan":
		fmt.Println(aad.RenderReclaimJSON())
	case "growth":
		growthCmd(os.Args[2:])
	case "serve":
		serveCmd(os.Args[2:])
	case "version", "--version":
		fmt.Println(aad.VersionJSON())
	case "-h", "--help", "help":
		usage()
	default:
		fmt.Fprintf(os.Stderr, "unknown command %q\n", os.Args[1])
		usage()
		os.Exit(2)
	}
}

func checkup(args []string) {
	fs := flag.NewFlagSet("checkup", flag.ExitOnError)
	asJSON := fs.Bool("json", false, "output as JSON")
	noParallel := fs.Bool("no-parallel", false, "run checks sequentially")
	only := fs.String("c", "", "comma-separated check names to run (default: all)")
	fs.Parse(args)

	var names []string
	if *only != "" {
		names = strings.Split(*only, ",")
	}
	rep := aad.RunCheckup(!*noParallel, names)

	// Log full checkups (names==nil) to checkup.ndjson for the menu-bar app.
	if names == nil {
		aad.LogCheckup(rep, "manual")
	}

	if *asJSON {
		fmt.Println(aad.RenderJSON(rep))
	} else {
		fmt.Print(aad.RenderText(rep))
	}
	if worstCritical(rep) {
		os.Exit(1)
	}
}

func worstCritical(rep aad.CheckupReport) bool {
	for _, r := range rep.Results {
		if r.WorstSeverity() == aad.CRITICAL {
			return true
		}
	}
	return false
}

// scoreCmd emits ScoreOutput JSON (for the menu-bar app). Reads the latest
// logged checkup; if there is none, runs a full checkup first.
func scoreCmd(args []string) {
	fs := flag.NewFlagSet("score", flag.ExitOnError)
	fs.Bool("json", true, "output as JSON (always on)")
	fs.Parse(args)
	if s := aad.LatestScoreJSON(); s != "" {
		fmt.Println(s)
		return
	}
	rep := aad.RunCheckup(true, nil)
	aad.LogCheckup(rep, "score")
	fmt.Println(aad.ScoreJSONFromReport(rep))
}

// growthCmd emits the fill-rate report; --sample first appends a hotspot
// snapshot (capped du over the watched reclaim paths).
func growthCmd(args []string) {
	fs := flag.NewFlagSet("growth", flag.ExitOnError)
	sample := fs.Bool("sample", false, "append a hotspot snapshot before reporting")
	fs.Parse(args)
	if *sample {
		if _, err := aad.SampleHotspots(); err != nil {
			fmt.Fprintln(os.Stderr, "hotspot sample:", err)
		}
	}
	fmt.Println(aad.RenderGrowthJSON())
}

// serveCmd runs the aad daemon (HTTP status API, like resource-sentinel).
func serveCmd(args []string) {
	fs := flag.NewFlagSet("serve", flag.ExitOnError)
	addr := fs.String("addr", "127.0.0.1:9342", "listen address")
	interval := fs.Duration("interval", 5*time.Minute, "checkup refresh interval")
	fs.Parse(args)
	fmt.Fprintf(os.Stderr, "aad serve on %s (refresh %s)\n", *addr, *interval)
	if err := aad.RunServer(*addr, *interval); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func pluginsCmd(args []string) {
	fs := flag.NewFlagSet("plugins", flag.ExitOnError)
	asJSON := fs.Bool("json", false, "output as JSON")
	fs.Parse(args)
	if *asJSON {
		fmt.Println(aad.RenderPluginsJSON())
	} else {
		fmt.Print(aad.RenderPlugins())
	}
}

func usage() {
	fmt.Fprintln(os.Stderr, "usage:")
	fmt.Fprintln(os.Stderr, "  aad checkup [--json] [--no-parallel] [-c name,name]")
	fmt.Fprintln(os.Stderr, "  aad score [--json]")
	fmt.Fprintln(os.Stderr, "  aad reclaim-plan   (always JSON; read-only, commands require human approval)")
	fmt.Fprintln(os.Stderr, "  aad growth [--sample]   (always JSON; fill rate, ETA to floor, growing paths)")
	fmt.Fprintln(os.Stderr, "  aad serve [--addr host:port] [--interval dur]")
	fmt.Fprintln(os.Stderr, "  aad plugins [--json]")
}
