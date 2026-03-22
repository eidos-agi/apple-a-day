---
id: 0008
title: 'Mac CLI tools: zero-dep claim is partially true'
status: open
evidence: HIGH
sources: 1
created: '2026-03-22'
---

## Claim

Verified dependency counts of top Mac CLI tools:

| Tool | Stars | Language | External Deps | Zero-dep? |
|------|-------|----------|--------------|-----------|
| Stats | 37,239 | Swift | 0 | YES |
| Mac-CLI | 9,049 | Shell | 0 | YES |
| mas-cli | 12,049 | Swift | 6 SPM packages | NO |
| trash-cli | 4,301 | Python | 2 (psutil, six) | NO |

The two highest-starred Mac tools (Stats, Mac-CLI) are genuinely zero-dep. They leverage OS frameworks directly. mas-cli has 6 Swift package deps despite being frequently cited as "lightweight."

## Supporting Evidence

> **Evidence: [HIGH]** — https://github.com/exelban/stats, https://github.com/guarinogabriel/Mac-CLI, https://github.com/mas-cli/mas/blob/main/Package.swift, retrieved 2026-03-22

## Caveats

None identified yet.
