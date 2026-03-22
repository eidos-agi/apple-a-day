"""Health check modules."""

from .crash_loops import check_crash_loops
from .dylib_health import check_dylib_health
from .kernel_panics import check_kernel_panics
from .disk_health import check_disk_health
from .memory_pressure import check_memory_pressure
from .launch_agents import check_launch_agents
from .homebrew import check_homebrew

ALL_CHECKS = [
    check_crash_loops,
    check_kernel_panics,
    check_dylib_health,
    check_memory_pressure,
    check_disk_health,
    check_launch_agents,
    check_homebrew,
]
