---
id: '0003'
title: README patterns that convert visitors to stars
status: open
evidence: MODERATE
sources: 1
created: '2026-03-22'
---

## Claim

Visitors decide to star or leave in ~5 seconds. README must follow this exact order:

1. **Hero line** — one sentence: "Keep your Mac healthy. One command, zero bloatware."
2. **Demo GIF/SVG** — record with `asciinema rec` → convert via `svg-term-cli` or `agg`. This is the single highest-impact README element. Repos with screenshots/GIFs get ~42% more stars.
3. **Badges (4-6 max):** PyPI version, Python 3.11+, License MIT, macOS 13+, GitHub stars, CI passing. More than 7 looks desperate.
4. **Quick install** — `pip install apple-a-day` — copy-pasteable in under 10 seconds
5. **Quick usage** — `aad checkup` with 2-3 example outputs
6. **Feature list** — scannable checkmarks or bullet points
7. **Comparison table** — "apple-a-day vs. CleanMyMac vs. iStat Menus" (free/open/CLI vs. $35+/closed/GUI)
8. **Contributing** — link to CONTRIBUTING.md
9. **License** — MIT

Keep README under 300 lines. Use `<details>` collapsible sections for verbose output examples.

## Supporting Evidence

> **Evidence: [MODERATE]** — https://rivereditor.com/blogs/write-perfect-readme-github-repo, https://www.markepear.dev/blog/github-readme-guide, retrieved 2026-03-22

## Caveats

None identified yet.
