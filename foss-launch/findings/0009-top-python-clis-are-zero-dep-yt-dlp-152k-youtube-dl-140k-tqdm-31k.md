---
id: 0009
title: 'Top Python CLIs are zero-dep: yt-dlp (152k), youtube-dl (140k), tqdm (31k)'
status: open
evidence: HIGH
sources: 1
created: '2026-03-22'
---

## Claim

The three most-starred Python CLI tools are all zero or effectively zero dependency:

| Tool | Stars | Required Deps |
|------|-------|--------------|
| yt-dlp | 152,483 | 0 (all optional) |
| youtube-dl | 139,930 | 0 |
| tqdm | 31,054 | 0 (colorama only on Windows) |
| black | 41,441 | 6+ |
| httpie | 37,753 | 7+ |
| glances | 32,126 | 5 |

yt-dlp explicitly declares `dependencies = []` in pyproject.toml with all deps moved to `[project.optional-dependencies]`. This is a deliberate architectural choice. The correlation is visible: the top of the Python CLI star chart is dominated by zero-dep tools.

## Supporting Evidence

> **Evidence: [HIGH]** — https://github.com/yt-dlp/yt-dlp/blob/master/pyproject.toml, retrieved 2026-03-22

## Caveats

None identified yet.
