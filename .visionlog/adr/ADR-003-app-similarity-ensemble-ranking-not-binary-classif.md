---
id: "ADR-003"
type: "decision"
title: "App similarity: ensemble ranking, not binary classification"
status: "proposed"
date: "2026-03-24"
---

## Context

Evaluated four approaches to detecting redundant/similar macOS apps: hardcoded synonym groups, ML logistic regression, ensemble of 6 signal voters, and temporal replacement detection. ML didn't beat synonym-only baseline. Ensemble ranks correctly but can't classify reliably (36% recall without synonyms).

## Decision

Use ensemble scoring as a ranking mechanism, not a classifier. Show "apps that may serve similar purposes" ranked by score. No threshold, no binary decision — informational list the user interprets.

## Why

- "Same purpose" is a semantic/human judgment, unsolvable with high accuracy from local signals alone
- Every discovery mechanism collapsed back into curated lists or couldn't distinguish purpose from build
- The ensemble ranks correctly — genuine pairs score above noise consistently
- Ranking avoids the false positive problem entirely
- Matches the project's read-only-by-default guardrail (informational, not prescriptive)

## What we tried and rejected

- sklearn logistic regression: didn't beat synonym-only baseline
- Localization strings alone: empty for Electron apps
- Framework fingerprints alone: tells you how apps are built, not what they do
- Pure ML without synonyms: 34.9% F1
