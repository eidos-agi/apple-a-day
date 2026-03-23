"""Health check modules."""

from .cleanup import check_cleanup
from .crash_loops import check_crash_loops
from .cpu_load import check_cpu_load
from .dylib_health import check_dylib_health
from .kernel_panics import check_kernel_panics
from .disk_health import check_disk_health
from .memory_pressure import check_memory_pressure
from .launch_agents import check_launch_agents
from .homebrew import check_homebrew
from .security import check_security
from .shutdown_causes import check_shutdown_causes
from .thermal import check_thermal
from .network import check_network

ALL_CHECKS = [
    check_crash_loops,
    check_kernel_panics,
    check_shutdown_causes,
    check_cpu_load,
    check_thermal,
    check_memory_pressure,
    check_dylib_health,
    check_disk_health,
    check_launch_agents,
    check_homebrew,
    check_security,
    check_network,
    check_cleanup,
]
