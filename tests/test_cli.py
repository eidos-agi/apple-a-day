"""Tests for CLI argument parsing and output format."""

import json
import platform
from io import StringIO
from unittest.mock import patch

import pytest

from apple_a_day.models import CheckResult, Finding, Severity


def _fake_report():
    """Create a synthetic CheckupReport for testing."""
    from apple_a_day.runner import CheckupReport

    return CheckupReport(
        results=[
            CheckResult(
                name="Crash Loops",
                findings=[Finding(check="crash_loops", severity=Severity.OK, summary="No crash loops")],
            ),
            CheckResult(
                name="Disk Health",
                findings=[
                    Finding(
                        check="disk_health",
                        severity=Severity.WARNING,
                        summary="Boot disk 87% full",
                        fix="Free up space",
                    )
                ],
            ),
        ],
        duration_ms=1234,
        mac_info={"os_version": "15.3", "cpu": "Apple M4", "memory_gb": 64},
    )


@pytest.mark.skipif(platform.system() != "Darwin", reason="macOS only")
class TestCLICheckup:
    def test_json_output_is_valid_json(self):
        with patch("apple_a_day.cli.run_all_checks", return_value=_fake_report()):
            from apple_a_day.cli import main

            with patch("sys.stdout", new_callable=StringIO) as mock_out:
                main(["checkup", "--json"])
                output = mock_out.getvalue()
                data = json.loads(output)
                assert "findings" in data
                assert "mac" in data
                assert "duration_ms" in data

    def test_json_fields_filter(self):
        with patch("apple_a_day.cli.run_all_checks", return_value=_fake_report()):
            from apple_a_day.cli import main

            with patch("sys.stdout", new_callable=StringIO) as mock_out:
                main(["checkup", "--json", "--fields", "severity,summary"])
                data = json.loads(mock_out.getvalue())
                for f in data["findings"]:
                    assert "fix" not in f
                    assert "severity" in f

    def test_min_severity_filter(self):
        with patch("apple_a_day.cli.run_all_checks", return_value=_fake_report()):
            from apple_a_day.cli import main

            with patch("sys.stdout", new_callable=StringIO) as mock_out:
                main(["checkup", "--json", "--min-severity", "warning"])
                data = json.loads(mock_out.getvalue())
                for f in data["findings"]:
                    assert f["severity"] in ("warning", "critical")

    def test_schema_output_is_valid_json(self):
        from apple_a_day.cli import main

        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            main(["schema"])
            data = json.loads(mock_out.getvalue())
            assert "checks" in data
