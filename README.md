# apple-a-day

[![PyPI](https://img.shields.io/pypi/v/apple-a-day)](https://pypi.org/project/apple-a-day/)
[![Python 3.11+](https://img.shields.io/pypi/pyversions/apple-a-day)](https://pypi.org/project/apple-a-day/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![macOS](https://img.shields.io/badge/platform-macOS-lightgrey)](https://github.com/eidos-agi/apple-a-day)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen)](https://pypi.org/project/apple-a-day/)

**Your Mac's immune system, operated by your AI agent.**

Zero dependencies. 13 checks. Plain english. Built for AI agents, friendly to humans.

```
pip install apple-a-day
aad checkup
```

<p align="center">
  <img src="https://raw.githubusercontent.com/eidos-agi/apple-a-day/main/demo/demo.svg" alt="apple-a-day checkup" width="700">
</p>

## The problem

Most people don't know why their Mac is slow. They feel the lag, hear the fans, see the beach ball — but they don't know that watchman has been crash-looping 600 times a day in the background, or that a broken Homebrew upgrade left 12 dylibs dangling, or that they're running 35GB of swap because Docker silently ate their RAM.

Apple's built-in tools don't help. Activity Monitor shows what's happening *right now*. Disk Utility tells you how full you are, not *why*. Console dumps raw logs nobody reads. There's no tool that looks at the whole picture and says, in plain english: "Here's what's wrong, here's why it matters, here's how to fix it."

People who can't keep their Mac clean aren't lazy — they're overwhelmed. They have 69 browser tabs open because each one represents an unfinished thought. They have apps they installed once and forgot. They have launch agents from software they uninstalled two years ago, still crash-looping, eating CPU. They don't know where their 1TB went because they've never heard of DerivedData or Docker.raw.

The commercial tools (CleanMyMac, DaisyDisk) charge $40/year and ask for Full Disk Access, which feels like malware. The free tools are either too technical (OnyX) or too simple (AppCleaner). None of them are built for the world we're entering — where your AI assistant should be able to check your Mac's health as part of its workflow.

## What apple-a-day does differently

**One command, full picture.** 13 checks run in parallel. Crash loops, kernel panics, memory pressure, disk health, broken libraries, orphaned services, thermals, security posture, network quality, stale apps. Every finding comes with a severity, an explanation, and a fix command you can copy-paste.

**Agent-native.** apple-a-day outputs structured JSON with a runtime schema. An AI agent can run `aad checkup --json`, read the findings, and act on them — without screen-scraping Activity Monitor or guessing. This is the first Mac health tool designed for AI agents as first-class consumers.

**Read-only by default.** apple-a-day diagnoses. It never modifies your system. It never asks for Full Disk Access. It never deletes anything. Fixes are suggested, not applied. You stay in control.

**Zero dependencies.** Pure Python stdlib and native macOS tools. No pip install pulls in half of PyPI. No compiled extensions. No C libraries. It works on any Mac with Python 3.11+.

## The bigger picture

apple-a-day is one layer in a Mac health stack:

- **apple-a-day** tells you what's wrong
- The **browser extension** shows you what's open and forgotten in Chrome
- **[space-hog](https://github.com/eidos-agi/space-hog)** tells you what to clean up and how much you'll reclaim
- An **AI agent** ties it all together — runs the checks, reads the findings, helps you act

The vitals daemon samples your system every 60 seconds, building a time-series log. When you ask "why was my Mac slow yesterday at 3pm?", the log already has the answer — load spikes, thermal throttling, swap escalation, the process that caused it, and how long it lasted.

## What it checks

| Module | What It Finds |
|--------|--------------|
| **Crash Loops** | Services dying repeatedly via DiagnosticReports |
| **Kernel Panics** | Panic logs decoded into human-readable causes |
| **Shutdown Causes** | Abnormal shutdown reasons (thermal, panic, forced) |
| **CPU Load** | Load average vs core count, top resource hogs |
| **Thermal** | Thermal pressure, kernel_task throttling |
| **Memory Pressure** | RAM pressure level and swap usage |
| **Disk Health** | APFS state, free space, Time Machine snapshot bloat |
| **Dylib Health** | Broken dynamic library links after brew upgrades |
| **Launch Agents** | Crash-looping, rogue, or forgotten launchd services |
| **Homebrew** | Outdated packages, doctor warnings, broken links |
| **Security** | SIP, Gatekeeper, FileVault, XProtect freshness |
| **Network** | Wi-Fi signal quality, speed test, responsiveness |
| **Cleanup** | Stale apps, orphaned launch agents, crash-loopers |

Every finding includes a severity, a plain-english explanation, and a fix command.

## Beyond the checkup

apple-a-day is more than a one-shot diagnostic:

| Feature | What |
|---------|------|
| **Vitals monitor** | Time-series sampling of CPU, thermal, swap — detects spikes and sustained load |
| **Health score** | 7-dimension matrix (stability, memory, storage, services, security, infra, network) with A-F grade |
| **Menu bar app** | macOS native SwiftUI app — stethoscope icon color-coded by health grade |
| **Browser extension** | Chrome extension tracking tab lifecycle, open tab count, stale tabs |
| **User profiling** | Detects developer type, installed tools, workspace shape — tailors findings accordingly |

## For AI Agents

```python
from apple_a_day.runner import run_all_checks

report = run_all_checks()
for r in report.results:
    for f in r.findings:
        if f.severity.value == "critical":
            print(f.summary, "->", f.fix)
```

Or via CLI:

```bash
# Get structured JSON for agent parsing
aad checkup --json --min-severity warning --fields severity,summary,fix

# Discover capabilities at runtime
aad schema

# Monitor vitals over time
aad monitor --once
aad vitals --minutes 60

# Health score
aad score --json
```

See [SKILL.md](SKILL.md) for the full agent-discoverable capability definition.

## Install

```bash
pip install apple-a-day
```

Or install from source:

```bash
git clone https://github.com/eidos-agi/apple-a-day.git
cd apple-a-day
pip install -e .
```

### Optional extras

```bash
pip install apple-a-day[rich]    # Rich table output
pip install apple-a-day[report]  # HTML report generation
```

### Vitals daemon

Run the vitals monitor as a background service that samples every 60 seconds:

```bash
aad install    # Install launchd daemon
aad status     # Check daemon status
aad uninstall  # Remove daemon
```

### Browser extension

Track browser tab activity and feed it into apple-a-day diagnostics:

```bash
# 1. Load browser/  as an unpacked extension in Chrome
# 2. Install the native messaging host:
aad browser install
aad browser status
```

## Ecosystem

apple-a-day is part of the [Eidos AGI](https://github.com/eidos-agi) Mac toolkit:

| Tool | Role |
|------|------|
| **apple-a-day** | Health diagnostics — what's wrong with your Mac |
| **[space-hog](https://github.com/eidos-agi/space-hog)** | Disk cleanup — what to remove and how much you'll reclaim |

Both tools share a Mac profile at `~/.config/eidos/mac-profile.json` and follow the same principles: zero dependencies, agent-native, read-only by default.

## Origin story

> *"Eat an apple on going to bed, and you'll keep the doctor from earning his bread."*
> -- Welsh proverb, Pembrokeshire, 1866

This tool was born from a real incident: a broken Homebrew dependency (`libboost_system.dylib`) caused Facebook's `watchman` to crash-loop **611 times in a single day** via a `KeepAlive` launchd plist. The crash loop likely triggered **9 kernel panics in 7 days** through watchdog timeouts. It took 20 minutes of manual forensics to figure out what happened.

apple-a-day would have caught it in seconds.

## Roadmap

- [ ] MCP server -- let Claude Code sessions query Mac health as a tool
- [ ] `aad fix` -- opt-in remediation with audit trail
- [ ] space-hog plugin -- disk cleanup as a first-class apple-a-day check
- [ ] Browser check module -- analyze tab data from the Chrome extension
- [x] ~~Thermal & power monitoring for Apple Silicon~~
- [x] ~~Network diagnostics (networkQuality, Wi-Fi signal)~~
- [x] ~~Security checks (SIP, Gatekeeper, XProtect, FileVault)~~
- [x] ~~PyPI release~~
- [x] ~~Menu bar app~~
- [x] ~~Browser extension~~
- [x] ~~Vitals time-series monitor~~

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

We welcome:
- New check modules for macOS-specific health issues
- Better plain-english explanations for existing findings
- Bug reports from real Mac issues you've encountered
- Suggestions for native macOS tools we should wrap

## Requirements

- macOS 13+ (Ventura or later)
- Python 3.11+
- Some checks benefit from Homebrew being installed

## License

MIT -- see [LICENSE](LICENSE).

---

Built by [Eidos AGI](https://github.com/eidos-agi). An apple a day keeps the doctor away.
