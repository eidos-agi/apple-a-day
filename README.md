# apple-a-day

**Mac health toolkit — keeps the doctor away.**

A single command that checks your Mac for crashes, broken services, memory pressure, disk issues, and more — then tells you what's wrong in plain english with a fix for every finding.

```
$ aad checkup
```

![apple-a-day screenshot](https://github.com/eidos-agi/apple-a-day/raw/main/docs/screenshot.png)

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

Every finding includes a severity, a plain-english explanation, and a fix command.

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
