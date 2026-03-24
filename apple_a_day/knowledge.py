"""Pre-canned plain-english explanations for Mac health concepts.

Every finding in apple-a-day can be tagged with a knowledge topic.
The report pulls the relevant explanation and shows it inline so
the reader understands what they're looking at without googling.
"""

# Each entry: short explanation, why it matters, how to fix
TOPICS: dict[str, dict[str, str]] = {
    "swap": {
        "what": (
            "Swap is overflow storage. When your Mac runs out of RAM, "
            "it moves data from memory onto your SSD. This is called "
            '"swapping." The data is still accessible, but reading from '
            "SSD is 10-100x slower than reading from RAM."
        ),
        "why": (
            "High swap means your Mac is doing real work on its slowest "
            "storage medium. Apps feel sluggish, typing lags, and the system "
            "can freeze momentarily when it has to swap in data it needs. "
            "On a 36 GB Mac, 16 GB of swap means you're effectively running "
            "a 52 GB workload — half of it at SSD speed."
        ),
        "fix": (
            "1. Reboot — clears all swap immediately\n"
            "2. Find the memory hog — open Activity Monitor → Memory tab, sort by Memory\n"
            "3. Common culprits: Docker Desktop (limit in Settings → Resources), "
            "browser tabs (each tab is a process), local LLMs (Ollama models hold 4-16 GB each), "
            "Xcode (DerivedData cache)\n"
            "4. Long-term: close apps you're not actively using, or add more RAM (not possible on Apple Silicon — it's soldered)"
        ),
    },
    "kernel_panic": {
        "what": (
            "A kernel panic is macOS's equivalent of a Blue Screen of Death. "
            "The kernel (the core of the OS) hit a state it can't recover from, "
            "so it crashes the entire system to prevent damage."
        ),
        "why": (
            "Kernel panics mean something is fundamentally wrong — not just "
            "an app crashing, but the OS itself failing. Repeated panics indicate "
            "a systemic issue: bad hardware, a buggy driver, or sustained resource "
            "exhaustion that starves critical system processes."
        ),
        "fix": (
            "1. Check the panic type (this report tells you)\n"
            "2. Watchdog timeout (most common): some process couldn't check in for 90+ seconds — "
            "usually caused by CPU starvation from too many processes or a hung driver\n"
            "3. Thermal emergency: Mac shut down to prevent hardware damage — improve cooling\n"
            "4. GPU memory: graphics driver bug — update macOS\n"
            "5. If panics happen daily: disconnect all USB devices and test, "
            "run Apple Diagnostics (hold D at boot), check for macOS updates"
        ),
    },
    "watchdog_timeout": {
        "what": (
            "macOS runs a watchdog daemon that checks in with the kernel every second. "
            "If the watchdog can't check in for ~90 seconds, the kernel assumes "
            "something is catastrophically wrong and panics."
        ),
        "why": (
            "This is the #1 cause of kernel panics on overloaded Macs. "
            "When CPU load is so high that even the watchdog can't get scheduled, "
            "the kernel has no choice but to assume a deadlock and crash. "
            "It's not a bug — it's a safety mechanism."
        ),
        "fix": (
            "1. Reduce CPU load — kill crash-looping services, close unnecessary apps\n"
            "2. Check for processes stuck in tight loops (Activity Monitor → CPU tab)\n"
            "3. If caused by a specific driver: check for updates or disconnect the device\n"
            "4. Run `aad checkup -c cpu_load -c launch_agents` to identify the load sources"
        ),
    },
    "crash_loop": {
        "what": (
            "A crash loop happens when a service crashes, macOS automatically restarts it "
            "(because it's configured with KeepAlive), it crashes again immediately, "
            "and this repeats indefinitely — hundreds or thousands of times per day."
        ),
        "why": (
            "Each restart consumes CPU, memory, and file descriptors. "
            "A service crashing 288 times/day means 288 process spawns, "
            "288 initialization attempts, 288 crash report writes. "
            "This sustained churn can push system load high enough to trigger "
            "watchdog timeouts and kernel panics."
        ),
        "fix": (
            "1. Stop the loop: `launchctl bootout gui/$(id -u) <plist_path>`\n"
            "2. Fix the root cause (missing dependency, bad config, missing env var)\n"
            "3. Or remove the KeepAlive setting from the plist if it's a periodic job\n"
            "4. Run `aad checkup -c launch_agents` to find all crash-looping services"
        ),
    },
    "memory_pressure": {
        "what": (
            "Memory pressure is macOS's measure of how hard the system is working "
            "to manage RAM. It has three levels: normal (green), warn (yellow), "
            "and critical (red). At critical, the system is actively killing "
            "background processes to free RAM."
        ),
        "why": (
            "At normal pressure, your Mac runs at full speed. At critical pressure, "
            "the system is in survival mode — closing apps, compressing memory, "
            "and writing to swap. Everything slows down. If you're seeing beach balls "
            "or app freezes, memory pressure is likely the cause."
        ),
        "fix": (
            "1. Close apps you're not using (especially browsers and Docker)\n"
            "2. Check Activity Monitor → Memory tab for the biggest consumers\n"
            "3. Reboot to reset memory state\n"
            "4. If chronic: you may be running a workload that exceeds your RAM"
        ),
    },
    "load_average": {
        "what": (
            "Load average is the number of processes waiting for CPU time, "
            "averaged over 1, 5, and 15 minutes. A load of 14 on a 14-core Mac "
            "means every core is busy. A load of 28 means processes are waiting "
            "in line — each process gets half the CPU time it needs."
        ),
        "why": (
            "Load average tells you if your Mac has enough CPU for what's running. "
            "When load far exceeds core count (e.g., 195 on a 14-core machine), "
            "everything slows down because processes compete for CPU time. "
            "Sustained high load is the root cause of most watchdog-timeout panics."
        ),
        "fix": (
            "1. Run `aad checkup -c cpu_load` to see which processes are consuming CPU\n"
            "2. Kill or pause non-essential heavy processes\n"
            "3. Check for crash-looping services that generate sustained load\n"
            "4. A spike that resolves quickly is normal (e.g., compiling). "
            "Sustained load > 3x cores for 15+ minutes is a problem."
        ),
    },
    "thermal_throttling": {
        "what": (
            "When your Mac gets too hot, it deliberately slows down the CPU "
            "to reduce heat output. This is called thermal throttling. "
            "The visible symptom is `kernel_task` consuming high CPU — "
            "it's generating idle cycles to force cooldown."
        ),
        "why": (
            "Thermal throttling protects your hardware from damage, but it means "
            "your Mac is running at a fraction of its rated speed. A Mac that can "
            "do 14 TFLOPS at full speed might only deliver 4 TFLOPS when throttled. "
            "If extreme, macOS will shut down entirely (thermal emergency)."
        ),
        "fix": (
            "1. Check ventilation — don't use on soft surfaces that block airflow\n"
            "2. Clean dust from vents (canned air)\n"
            "3. Reduce workload or spread it over time\n"
            "4. Use a cooling pad for sustained heavy work\n"
            "5. If persistent: SMC reset (shut down, hold power 10s, release, wait 5s, boot)"
        ),
    },
    "disk_pressure": {
        "what": (
            "macOS needs free disk space to function. It uses free space for "
            "swap files, temporary files, app caches, and system updates. "
            "When free space drops below ~10% of total, performance degrades."
        ),
        "why": (
            "Low disk space causes a cascade: swap files can't grow when RAM is full "
            "(leading to app crashes), system updates fail, Time Machine can't create "
            "local snapshots, and APFS becomes less efficient at wear-leveling the SSD."
        ),
        "fix": (
            "1. Clear Time Machine snapshots: `sudo tmutil thinlocalsnapshots / 9999999999 1`\n"
            "2. Docker: `docker system prune -a` (removes unused images/containers)\n"
            "3. Xcode: delete ~/Library/Developer/Xcode/DerivedData\n"
            "4. Homebrew: `brew cleanup`\n"
            "5. Check ~/Library/Caches for large app caches\n"
            "6. Use `aad checkup -c disk_health` for specific recommendations"
        ),
    },
    "orphaned_agent": {
        "what": (
            "An orphaned launch agent is a background service that's still registered "
            "with macOS but whose parent app has been uninstalled. The agent's binary "
            "is missing, so it fails every time macOS tries to run it."
        ),
        "why": (
            "Orphaned agents waste system resources on failed launches and clutter "
            "the launchd service list. With KeepAlive enabled, they can become "
            "crash loops. They're harmless individually but accumulate over time."
        ),
        "fix": (
            "1. Unload: `launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/<label>.plist`\n"
            "2. Delete the plist file\n"
            "3. Run `aad checkup -c cleanup` to find all orphaned agents"
        ),
    },
    "shutdown_cause": {
        "what": (
            "Every time your Mac shuts down, macOS logs a numeric cause code. "
            "Code 3 or 5 means a clean shutdown. Negative codes indicate problems: "
            "-1/-2 is a kernel panic, -3 is thermal emergency, -128 is forced power-off."
        ),
        "why": (
            "Shutdown causes are the most reliable way to tell if your Mac is crashing "
            "vs. shutting down normally. A series of clean shutdowns (code 3/5) means "
            "the system is stable. A series of -1 or -2 codes means kernel panics."
        ),
        "fix": (
            "1. Run `aad checkup -c shutdown_causes` to see recent history\n"
            "2. Cross-reference with `aad vitals` to see what was happening before the crash\n"
            "3. See the kernel_panic topic for specific remediation"
        ),
    },
}


def get_topic(key: str) -> dict[str, str] | None:
    """Get a knowledge topic by key."""
    return TOPICS.get(key)


def match_topics(summary: str, check_name: str) -> list[str]:
    """Given a finding summary and check name, return relevant topic keys."""
    summary_lower = summary.lower()
    check_lower = check_name.lower()
    matched = []

    # Direct check-name mapping
    check_map = {
        "kernel panics": ["kernel_panic"],
        "crash loops": ["crash_loop"],
        "memory pressure": ["memory_pressure"],
        "cpu load": ["load_average"],
        "thermal": ["thermal_throttling"],
        "disk health": ["disk_pressure"],
        "shutdown causes": ["shutdown_cause"],
        "cleanup": ["orphaned_agent"],
        "launch agents": ["crash_loop"],
    }
    if check_lower in check_map:
        matched.extend(check_map[check_lower])

    # Keyword matching in summary
    if "swap" in summary_lower:
        if "swap" not in matched:
            matched.append("swap")
    if "watchdog" in summary_lower:
        if "watchdog_timeout" not in matched:
            matched.append("watchdog_timeout")
    if "thermal" in summary_lower or "throttl" in summary_lower:
        if "thermal_throttling" not in matched:
            matched.append("thermal_throttling")
    if "orphan" in summary_lower:
        if "orphaned_agent" not in matched:
            matched.append("orphaned_agent")

    return matched
