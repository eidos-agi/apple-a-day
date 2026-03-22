"""Shared data models for health checks."""

from dataclasses import dataclass, field
from enum import Enum


class Severity(Enum):
    OK = "ok"
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Finding:
    """A single health finding."""

    check: str
    severity: Severity
    summary: str
    details: str = ""
    fix: str = ""

    @property
    def icon(self) -> str:
        return {
            Severity.OK: "✓",
            Severity.INFO: "ℹ",
            Severity.WARNING: "⚠",
            Severity.CRITICAL: "✗",
        }[self.severity]


@dataclass
class CheckResult:
    """Result from a health check module."""

    name: str
    findings: list[Finding] = field(default_factory=list)

    @property
    def worst_severity(self) -> Severity:
        if not self.findings:
            return Severity.OK
        return max(self.findings, key=lambda f: list(Severity).index(f.severity)).severity
