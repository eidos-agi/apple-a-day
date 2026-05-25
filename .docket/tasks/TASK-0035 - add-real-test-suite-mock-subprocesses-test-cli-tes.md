---
id: TASK-0035
title: Add real test suite — mock subprocesses, test CLI, test log rotation (BRUTAL-009)
status: Done
created: '2026-04-02'
priority: high
milestone: MS-0003
tags:
  - brutal-forge
  - testing
updated: '2026-04-02'
---
Current test suite: 3 functions, no mocking, tests are slow and non-deterministic. Add subprocess mocking per check, CLI arg parsing tests, log rotation tests, score computation tests.

Added test_cli.py (4 tests: JSON output, field filtering, severity filtering, schema), test_log.py (5 tests: score matrix, log rotation), test_vitals.py (4 tests: read backwards, empty file, missing file, old samples). Total: 16 tests, 0.15s, all mocked.
