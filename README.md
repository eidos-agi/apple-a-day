# apple-a-day

[![PyPI](https://img.shields.io/pypi/v/apple-a-day)](https://pypi.org/project/apple-a-day/)
[![Python 3.11+](https://img.shields.io/pypi/pyversions/apple-a-day)](https://pypi.org/project/apple-a-day/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![macOS](https://img.shields.io/badge/platform-macOS-lightgrey)](https://github.com/eidos-agi/apple-a-day)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen)](https://pypi.org/project/apple-a-day/)

**Agent-native Mac health toolkit — keeps the doctor away.**

Zero dependencies. 9 checks. Plain english. Built for AI agents, friendly to humans.

```
pip install apple-a-day
aad checkup
```

<p align="center">
  <img src="https://raw.githubusercontent.com/eidos-agi/apple-a-day/main/demo/demo.svg" alt="apple-a-day checkup" width="700">
</p>

## What it checks

| Module | What It Finds |
|--------|--------------|
| **Crash Loops** | Services dying repeatedly via DiagnosticReports |
| **Kernel Panics** | Panic logs decoded into human-readable causes |
| **Dylib Health** | Broken dynamic library links after brew upgrades |
| **Memory Pressure** | RAM pressure level and swap usage |
| **Disk Health** | APFS state, free space, Time Machine snapshot bloat |
| **Launch Agents** | Crash-looping, rogue, or forgotten launchd services |
| **Homebrew** | Outdated packages, doctor warnings, broken links |
| **Security** | SIP, Gatekeeper, FileVault, XProtect freshness |
| **Network** | Wi-Fi signal quality, speed test, responsiveness |

Every finding includes a severity, a plain-english explanation, and a fix command.

## For AI Agents

```python
from apple_a_day.runner import run_all_checks

report = run_all_checks()
for r in report.results:
    for f in r.findings:
        if f.severity.value == "critical":
            print(f.summary, "→", f.fix)
```

Or via CLI:

```bash
# Get structured JSON for agent parsing
aad checkup --json --min-severity warning --fields severity,summary,fix

# Discover capabilities at runtime
aad schema
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

## Usage

Run all checks:

```bash
aad checkup
```

JSON output (for scripts or piping):

```bash
aad checkup --json
```

## Why "apple-a-day"?

> *"Eat an apple on going to bed, and you'll keep the doctor from earning his bread."*
>
> — Welsh proverb, Pembrokeshire, 1866

Prevention over treatment. Don't wait until your Mac is crashing — run the check daily and you won't need the doctor at all. The tool runs silently every morning, scoring your Mac's health across 7 dimensions. By the time you ask "why is my Mac slow?", the log already has the answer.

## Origin story

This tool was born from a real incident: a broken Homebrew dependency (`libboost_system.dylib`) caused Facebook's `watchman` to crash-loop **611 times in a single day** via a `KeepAlive` launchd plist. The crash loop likely triggered **9 kernel panics in 7 days** through watchdog timeouts. It took 20 minutes of manual forensics to figure out what happened.

apple-a-day would have caught it in seconds.

## Design principles

- **Mac-native** — uses `otool`, `diskutil`, `launchctl`, `powermetrics`, and other macOS-specific tools directly. No cross-platform abstraction.
- **Plain english** — doesn't just report "exit code -6". Explains it means SIGABRT from a missing dylib and tells you to `brew reinstall`.
- **Always actionable** — every finding includes a fix or next step.
- **Read-only by default** — `aad checkup` never modifies your system. Future `aad fix` will require explicit opt-in.

## Roadmap

- [ ] MCP server — let Claude Code sessions query Mac health as a tool
- [ ] `aad fix` — opt-in remediation with confirmation for each fix
- [ ] Thermal & power monitoring for Apple Silicon
- [ ] Network diagnostics (networkQuality, Wi-Fi signal)
- [ ] Security checks (SIP, Gatekeeper, XProtect, FileVault)
- [ ] SSD health via smartctl
- [ ] PyPI release

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

MIT — see [LICENSE](LICENSE).

---

Built by [Eidos AGI](https://github.com/eidos-agi). An apple a day keeps the doctor away.
