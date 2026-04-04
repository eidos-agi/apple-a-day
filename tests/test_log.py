"""Tests for log rotation and scoring."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from apple_a_day.models import CheckResult, Finding, Severity, compute_score_matrix


class TestScoreMatrix:
    def test_all_ok_gives_a(self):
        results = [
            CheckResult(
                name="Crash Loops",
                findings=[Finding(check="t", severity=Severity.OK, summary="ok")],
            ),
            CheckResult(
                name="CPU Load",
                findings=[Finding(check="t", severity=Severity.OK, summary="ok")],
            ),
        ]
        data = compute_score_matrix(results)
        assert data["grade"] == "A"
        assert data["score"] >= 90

    def test_critical_drops_score(self):
        results = [
            CheckResult(
                name="Crash Loops",
                findings=[Finding(check="t", severity=Severity.CRITICAL, summary="bad")],
            ),
        ]
        data = compute_score_matrix(results)
        assert data["matrix"]["stability"] == 0
        assert data["score"] < 90

    def test_all_9_dimensions_present(self):
        data = compute_score_matrix([])
        assert len(data["matrix"]) == 9
        for dim in ["stability", "cpu", "thermal", "memory", "storage", "services", "security", "infra", "network"]:
            assert dim in data["matrix"]


class TestLogRotation:
    def test_rotation_at_size_limit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir)
            log_file = log_dir / "checkup.ndjson"

            # Write a file just over the limit
            log_file.write_text("x" * (11 * 1024 * 1024))  # 11 MB

            with (
                patch("apple_a_day.log.LOG_DIR", log_dir),
                patch("apple_a_day.log.CURRENT_LOG", log_file),
            ):
                from apple_a_day.log import _rotate_if_needed

                _rotate_if_needed()

                # Original should be gone, rotated file should exist
                assert not log_file.exists()
                rotated = list(log_dir.glob("checkup-*.ndjson"))
                assert len(rotated) == 1

    def test_no_rotation_under_limit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir)
            log_file = log_dir / "checkup.ndjson"
            log_file.write_text("small\n")

            with (
                patch("apple_a_day.log.LOG_DIR", log_dir),
                patch("apple_a_day.log.CURRENT_LOG", log_file),
            ):
                from apple_a_day.log import _rotate_if_needed

                _rotate_if_needed()
                assert log_file.exists()
