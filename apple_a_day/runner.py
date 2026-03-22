"""Run all health checks and collect results."""

from .checks import ALL_CHECKS
from .models import CheckResult


def run_all_checks() -> list[CheckResult]:
    """Execute every registered health check and return results."""
    results = []
    for check_fn in ALL_CHECKS:
        try:
            results.append(check_fn())
        except Exception as e:
            results.append(CheckResult(name=check_fn.__name__))
    return results
