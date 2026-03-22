"""Tests for check modules — verify they run without crashing."""

import platform

import pytest

from apple_a_day.checks import ALL_CHECKS
from apple_a_day.models import CheckResult


@pytest.mark.skipif(platform.system() != "Darwin", reason="macOS only")
class TestChecksRun:
    """Each check should return a CheckResult without raising."""

    @pytest.mark.parametrize("check_fn", ALL_CHECKS, ids=lambda fn: fn.__name__)
    def test_check_returns_result(self, check_fn):
        result = check_fn()
        assert isinstance(result, CheckResult)
        assert result.name
        assert len(result.findings) > 0

    @pytest.mark.parametrize("check_fn", ALL_CHECKS, ids=lambda fn: fn.__name__)
    def test_findings_have_summaries(self, check_fn):
        result = check_fn()
        for f in result.findings:
            assert f.summary, f"Finding in {result.name} has empty summary"
