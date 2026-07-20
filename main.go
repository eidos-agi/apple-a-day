// Command aad is the Go rewrite of apple-a-day — read-only macOS health checks.
package main

import (
	"flag"
	"fmt"
	"os"
	"strings"

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
	fmt.Fprintln(os.Stderr, "  aad plugins [--json]")
}
