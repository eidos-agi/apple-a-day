---
id: '0010'
title: pip vendored rich rather than depending on it — the gold standard compromise
status: open
evidence: HIGH
sources: 1
created: '2026-03-22'
---

## Claim

pip's approach to rich is the canonical case study (pypa/pip#10423):

- pip wanted beautiful output but refused to impose rich as an install-time dependency on every Python user
- Solution: vendored rich into `src/pip/_vendor/rich/`, also vendored pygments, tree-shook unused parts
- This gives beautiful output with zero install-time dependency cost

Meanwhile, cookiecutter added rich as a core dep without discussion. Now facing an open issue (cookiecutter#2078) from the Kedro maintainer requesting removal because rich "causes a lot of issues outside of standard terminal and is not useful in non-interactive environments (i.e. CI/production)."

Three viable strategies, ranked by adoption success:
1. **Zero deps** (yt-dlp) — maximum portability
2. **Vendor it** (pip) — get the feature, own the code
3. **Make it optional** (yt-dlp's optional-dependencies) — power users opt in

Hard-requiring rich or click is the least preferred strategy among high-adoption projects.

## Supporting Evidence

> **Evidence: [HIGH]** — https://github.com/pypa/pip/issues/10423, https://github.com/cookiecutter/cookiecutter/issues/2078, retrieved 2026-03-22

## Caveats

None identified yet.
