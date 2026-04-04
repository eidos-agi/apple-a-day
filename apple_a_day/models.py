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
class CheckError:
    """Structured error when a check itself fails to run."""

    check: str
    error_code: str
    message: str
    suggestion: str = ""

    def to_dict(self) -> dict:
        d = {"check": self.check, "error_code": self.error_code, "message": self.message}
        if self.suggestion:
            d["suggestion"] = self.suggestion
        return d


# Common error codes
ERR_TIMEOUT = "TIMEOUT"
ERR_PERMISSION = "PERMISSION_DENIED"
ERR_TOOL_MISSING = "TOOL_NOT_FOUND"
ERR_PARSE = "PARSE_ERROR"
ERR_UNKNOWN = "UNKNOWN_ERROR"


@dataclass
class CheckResult:
    """Result from a health check module."""

    name: str
    findings: list[Finding] = field(default_factory=list)
    errors: list[CheckError] = field(default_factory=list)

    @property
    def worst_severity(self) -> Severity:
        if not self.findings:
            return Severity.OK
        return max(self.findings, key=lambda f: list(Severity).index(f.severity)).severity


# --- Health score matrix (shared across log.py, report.py, cli.py) ---

DIMENSION_CHECKS = {
    "stability": ["Crash Loops", "Kernel Panics", "Shutdown Causes"],
    "cpu": ["CPU Load"],
    "thermal": ["Thermal"],
    "memory": ["Memory Pressure"],
    "storage": ["Disk Health"],
    "services": ["Launch Agents"],
    "security": ["Security"],
    "infra": ["Dynamic Library Health", "Homebrew"],
    "network": ["Network"],
}

DIMENSION_WEIGHTS = {
    "stability": 3,
    "cpu": 3,
    "memory": 2,
    "thermal": 2,
    "storage": 2,
    "services": 2,
    "security": 1,
    "infra": 1,
    "network": 1,
}

DIMENSION_LABELS = {
    "stability": "Stability",
    "cpu": "CPU",
    "thermal": "Thermal",
    "memory": "Memory",
    "storage": "Storage",
    "services": "Services",
    "security": "Security",
    "infra": "Infra",
    "network": "Network",
}


def compute_score_matrix(results: list["CheckResult"]) -> dict:
    """Compute the health score matrix from check results.

    Returns: {"matrix": {dim: 0-100}, "score": 0-100, "grade": "A"-"F"}
    """
    check_scores = {}
    for r in results:
        score = 100
        for f in r.findings:
            s = f.severity.value
            if s == "critical":
                score = min(score, 0)
            elif s == "warning":
                score = min(score, 50)
            elif s == "info":
                score = min(score, 80)
        check_scores[r.name] = score

    matrix = {}
    for dim, checks in DIMENSION_CHECKS.items():
        scores = [check_scores.get(c, 100) for c in checks]
        matrix[dim] = min(scores) if scores else 100

    weighted_sum = sum(matrix.get(d, 100) * w for d, w in DIMENSION_WEIGHTS.items())
    total_weight = sum(DIMENSION_WEIGHTS.values())
    overall = round(weighted_sum / total_weight)

    if overall >= 90:
        grade = "A"
    elif overall >= 75:
        grade = "B"
    elif overall >= 50:
        grade = "C"
    elif overall >= 25:
        grade = "D"
    else:
        grade = "F"

    return {"matrix": matrix, "score": overall, "grade": grade}
