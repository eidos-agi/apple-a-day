"""Tests for data models."""

from apple_a_day.models import CheckResult, Finding, Severity


def test_finding_icons():
    assert Finding(check="t", severity=Severity.OK, summary="ok").icon == "✓"
    assert Finding(check="t", severity=Severity.CRITICAL, summary="bad").icon == "✗"


def test_check_result_worst_severity():
    r = CheckResult(name="test", findings=[
        Finding(check="t", severity=Severity.OK, summary="fine"),
        Finding(check="t", severity=Severity.WARNING, summary="warn"),
    ])
    assert r.worst_severity == Severity.WARNING


def test_check_result_empty():
    r = CheckResult(name="test")
    assert r.worst_severity == Severity.OK
