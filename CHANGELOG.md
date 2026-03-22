# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
