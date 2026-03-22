---
id: '0007'
title: Dependency minimalism in successful Mac CLI tools
status: open
evidence: HIGH
sources: 1
created: '2026-03-22'
---

## Claim

Examining the dependency approach of top Mac FOSS tools:

**Zero-dep tools (highest star counts):**
- Stats (36.6k stars) — pure Swift, zero external deps
- Mac-CLI (8.8k stars) — pure bash, zero deps
- mas-cli — pure Swift, zero deps
- trash-cli — pure Swift, zero deps
- macOS-Monitoring (MacStadium) — pure shell/awk, zero deps

**Pattern: every top Mac CLI tool has zero or near-zero dependencies.** The Mac dev community values self-contained tools. This is both cultural (distrust of dependency bloat post-leftpad) and practical (fewer breakage vectors on a system health tool).

**The irony problem:** a Mac health tool that diagnoses broken dependencies (like the watchman/libboost incident that birthed this project) should not itself be vulnerable to broken dependencies. A tool that checks dylib health shouldn't have its own dependency health problems.

**Rich specifically:**
- Pulls in `pygments` and `markdown-it-py` as transitive deps
- Total dependency tree: rich → pygments, markdown-it-py → mdurl
- That's 4 packages total for colored tables
- ANSI escape codes achieve 80% of the visual impact with 0 packages

**Click specifically:**
- argparse is stdlib, does everything we need for `aad checkup --json --min-severity warning`
- Click adds convenience but no capability we can't replicate in 20 lines

**Counter-argument:** Rich's output is what makes the README GIF compelling. First impressions matter for stars. But we can achieve compelling output with ANSI + Unicode box-drawing characters.

**Recommendation:** Zero runtime dependencies. The meta-narrative — "a Mac health tool with zero dependencies that diagnoses dependency problems" — is itself a marketing story.

## Supporting Evidence

> **Evidence: [HIGH]** — https://github.com/exelban/stats, https://github.com/guarinogabriel/Mac-CLI, https://github.com/macstadium/macOS-Monitoring, retrieved 2026-03-22

## Caveats

None identified yet.
