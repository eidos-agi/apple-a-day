# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.1] - 2026-03-24

### Added
- macOS menu bar app (SwiftUI MenuBarExtra) with stethoscope icon, color-coded by health grade
- Health panel: overall grade card, 9 dimension scores, active findings, vitals sparklines
- Reports panel: generate new reports with spinner, browse timestamped report history
- Launch at login via LaunchAgent (`make install-login`)
- App icon: SF Symbol stethoscope + apple accent, rendered natively via AppKit
- Ensemble app similarity scorer: 6 independent voters (brew descriptions, UI vocabulary, category, UTIs, runtime/frameworks, URL schemes)
- Feature extraction module: runtime detection, framework fingerprinting, Homebrew descriptions, localization vocabulary
- Replacement detection: temporal usage patterns from Spotlight metadata
- Report section "Apps That May Serve Similar Purposes" — ranked pairs, not binary classification
- `make roll` deploys menu bar app to /Applications with codesign + lsregister
- Timestamped HTML reports saved to `~/.config/eidos/aad-logs/reports/`

### Changed
- "Redundant Apps" report section renamed to "Similar Apps" — informational ranking instead of prescriptive removal
- App similarity heuristic enriched with runtime match and URL scheme overlap signals

## [0.2.0] - 2026-03-22

### Added
- Security check module: SIP, Gatekeeper, FileVault, XProtect freshness
- Network check module: Wi-Fi signal (RSSI, SNR, channel, PHY) + speed test via networkQuality
- `aad schema` command for agent runtime introspection
- SKILL.md for agent discoverability
- `--fields` flag to limit JSON output fields (context window discipline)
- Structured error JSON (CheckError model with error codes)
- ANSI terminal formatter as zero-dependency default

### Changed
- **Zero runtime dependencies** — click and rich removed from core
- CLI rewritten from click to stdlib argparse
- Rich moved to optional `[rich]` extra — auto-detected at runtime
- Errors are now structured JSON, not swallowed exceptions

## [0.1.0] - 2026-03-22

### Added
- Initial release
- 7 health check modules: crash loops, kernel panics, dylib health, memory pressure, disk health, launch agents, homebrew
- CLI entry point `aad checkup` with Rich-formatted terminal output
- JSON output via `aad checkup --json`
- Parallel check execution via `--no-parallel` flag to disable
- Severity filtering via `--min-severity`
- Selective checks via `--check/-c` flag
- Mac info header (OS version, CPU, RAM) in output
- Timing display in summary
