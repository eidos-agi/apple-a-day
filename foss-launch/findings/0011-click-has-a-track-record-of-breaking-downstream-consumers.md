---
id: '0011'
title: Click has a track record of breaking downstream consumers
status: open
evidence: HIGH
sources: 1
created: '2026-03-22'
---

## Claim

Click's real cost is behavioral breaking changes on upgrade:

- Click 8.0 removed `get_terminal_size` from `click.termui`, broke spaCy (explosion/spaCy#10564)
- Click 8.2.0 broke miiocli entirely (python-miio#2031)
- Click 8.3.x introduced new boolean flag behavior breaking downstream projects
- 73 issues mentioning "breaking change" over the project's life

Rich has a lighter tree (4 packages: rich + pygments + markdown-it-py + mdurl) and fewer breaking changes, but its output format instability breaks snapshot tests on upgrade.

For apple-a-day, Click is replaceable with ~20 lines of argparse. Rich is harder to replace but the "afternoon of programming" principle (Carl Johnson, HN #24123878) applies: ANSI escape codes + Unicode box-drawing achieve 80% of the visual impact.

## Supporting Evidence

> **Evidence: [HIGH]** — https://github.com/explosion/spaCy/issues/10564, https://github.com/rytilahti/python-miio/issues/2031, https://click.palletsprojects.com/en/stable/changes/, https://news.ycombinator.com/item?id=24123878, retrieved 2026-03-22

## Caveats

None identified yet.
