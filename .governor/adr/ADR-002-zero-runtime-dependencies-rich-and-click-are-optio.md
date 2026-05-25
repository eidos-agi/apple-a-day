---
id: "ADR-002"
type: "decision"
title: "Zero runtime dependencies — rich and click are optional"
status: "accepted"
date: "2026-03-22"
source_research_id: "bad85d8e-be67-4e9e-bb3a-c25eb71bd311"
---

## Context

Research (foss-launch findings 0007-0011) showed:
- Top Python CLIs are zero-dep: yt-dlp (152k stars), youtube-dl (140k), tqdm (31k)
- pip vendored rich rather than depending on it
- Click has a track record of breaking downstream consumers (spaCy, miiocli, others)
- A Mac health tool that diagnoses broken dependencies should not itself have dependency problems

## Decision

Zero runtime dependencies. `dependencies = []` in pyproject.toml.
- Drop click → use argparse (stdlib)
- Move rich to optional: `pip install apple-a-day[rich]`
- Default output uses ANSI escape codes + Unicode box-drawing
- Follow the yt-dlp pattern: core works with nothing but stdlib Python

## Consequences

- Need to rewrite CLI from click to argparse (~30 lines)
- Need to write a thin ANSI formatter as default renderer
- Rich tables available via `apple-a-day[rich]` for humans who want them
- Install is instant, no transitive deps, no supply chain risk
- Marketing angle: "zero-dependency Mac health tool that diagnoses dependency problems"
