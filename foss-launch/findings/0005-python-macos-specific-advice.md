---
id: '0005'
title: Python + macOS specific advice
status: open
evidence: HIGH
sources: 1
created: '2026-03-22'
---

## Claim

**Distribution:**
- Start with a Homebrew tap (`eidos-agi/homebrew-tap`) — no approval needed, instant
- Submit to homebrew-core after 50+ stars and proven stability
- `pipx install apple-a-day` handles venv automatically — recommend this over raw pip
- Homebrew Python formula requires bundling deps in virtualenv via `Language::Python::Virtualenv`

**macOS data sources (no sudo required):**
- `system_profiler SPBatteryDataType -json` — battery health, cycle count
- `system_profiler SPHardwareDataType -json` — hardware model, memory
- `system_profiler SPStorageDataType -json` — disk usage, SMART status
- `pmset -g batt` — battery charge state
- All `sysctl`, `diskutil`, `vm_stat`, `otool` — no sudo needed
- `powermetrics` needs sudo — make it optional, degrade gracefully

**Testing:**
- GitHub Actions has macOS runners: macos-13 (Intel), macos-14+ (ARM)
- Mock `system_profiler` output in tests for CI reproducibility
- Test on both Intel and Apple Silicon

## Supporting Evidence

> **Evidence: [HIGH]** — https://docs.brew.sh/Python-for-Formula-Authors, https://docs.brew.sh/Formula-Cookbook, https://packaging.python.org/en/latest/guides/writing-pyproject-toml/, retrieved 2026-03-22

## Caveats

None identified yet.
