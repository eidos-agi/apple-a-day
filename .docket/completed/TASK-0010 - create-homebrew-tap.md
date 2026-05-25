---
id: TASK-0010
title: Create Homebrew tap
status: Done
created: '2026-03-22'
priority: medium
milestone: MS-0002
tags:
  - release
  - distribution
definition-of-done:
  - eidos-agi/homebrew-tap repo exists
  - brew install eidos-agi/tap/apple-a-day works
  - formula bundles Python deps in virtualenv
visionlog_goal_id: GOAL-005
updated: '2026-03-22'
---
Create eidos-agi/homebrew-tap repo with formula for apple-a-day. brew tap eidos-agi/tap && brew install apple-a-day works.

**Completion notes:** eidos-agi/homebrew-tap created (public). Formula at Formula/apple-a-day.rb. brew tap eidos-agi/tap && brew install apple-a-day verified working.
