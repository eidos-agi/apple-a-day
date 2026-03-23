"""Lightweight vitals sampler — the time-series backbone of apple-a-day.

Samples system vitals every N seconds and appends to a rolling NDJSON log.
Each sample is ~200 bytes. At 1 sample/minute, a day is ~288 KB.

The CPU load, thermal, and memory checks read this history to detect
patterns that point-in-time snapshots miss: spikes, sustained overload,
thermal ramps, memory pressure escalation.

Usage:
    # Single sample (for launchd / cron)
    aad monitor --once

    # Continuous sampling (foreground)
    aad monitor --interval 60

    # Read recent samples programmatically
    from apple_a_day.vitals import read_vitals
    samples = read_vitals(minutes=30)
"""

import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

LOG_DIR = Path.home() / ".config" / "eidos" / "aad-logs"
VITALS_LOG = LOG_DIR / "vitals.ndjson"
MAX_VITALS_SIZE = 5 * 1024 * 1024  # 5 MB (~25 days at 1/min), then rotate


def sample() -> dict:
    """Take a single vitals sample. Fast — targets <500ms."""
    s = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "load": list(os.getloadavg()),
        "cores": os.cpu_count() or 0,
    }

    # Top 5 CPU consumers (fast — no subprocess timeout concern)
    try:
        out = subprocess.run(
            ["ps", "-eo", "pcpu,comm", "-r"],
            capture_output=True, text=True, timeout=5,
        )
        if out.returncode == 0:
            hogs = []
            for line in out.stdout.strip().split("\n")[1:6]:
                parts = line.strip().split(None, 1)
                if len(parts) == 2:
                    cpu = float(parts[0])
                    if cpu < 5:
                        break
                    name = parts[1].rsplit("/", 1)[-1]
                    hogs.append([round(cpu, 1), name])
            s["top"] = hogs
    except (subprocess.TimeoutExpired, OSError):
        pass

    # Thermal pressure level — try sysctl (Intel), fall back to pmset (Apple Silicon)
    try:
        out = subprocess.run(
            ["sysctl", "-n", "kern.thermalpressurelevel"],
            capture_output=True, text=True, timeout=3,
        )
        if out.returncode == 0 and out.stdout.strip().isdigit():
            s["thermal"] = int(out.stdout.strip())
    except (subprocess.TimeoutExpired, OSError):
        pass

    if "thermal" not in s:
        try:
            out = subprocess.run(
                ["pmset", "-g", "therm"],
                capture_output=True, text=True, timeout=3,
            )
            if out.returncode == 0:
                lower = out.stdout.lower()
                if "no thermal warning" in lower and "no performance warning" in lower:
                    s["thermal"] = 0
                else:
                    s["thermal"] = 2  # elevated
        except (subprocess.TimeoutExpired, OSError):
            pass

    # Memory pressure (quick sysctl, not the slow memory_pressure tool)
    try:
        out = subprocess.run(
            ["sysctl", "vm.swapusage"],
            capture_output=True, text=True, timeout=3,
        )
        if out.returncode == 0 and "used" in out.stdout:
            used_str = out.stdout.split("used = ")[1].split(" ")[0]
            s["swap_mb"] = round(float(used_str.rstrip("M")), 0)
    except (subprocess.TimeoutExpired, OSError, ValueError, IndexError):
        pass

    return s


def record(s: dict | None = None) -> Path:
    """Sample (if needed) and append to vitals log."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    _rotate_if_needed()

    if s is None:
        s = sample()

    with open(VITALS_LOG, "a") as f:
        f.write(json.dumps(s, separators=(",", ":")) + "\n")
    return VITALS_LOG


def _rotate_if_needed():
    """Rotate vitals log if it exceeds max size."""
    if VITALS_LOG.exists() and VITALS_LOG.stat().st_size > MAX_VITALS_SIZE:
        rotated = LOG_DIR / f"vitals-{datetime.now().strftime('%Y%m%d-%H%M%S')}.ndjson"
        VITALS_LOG.rename(rotated)


def read_vitals(minutes: int = 60) -> list[dict]:
    """Read vitals samples from the last N minutes."""
    if not VITALS_LOG.exists():
        return []

    cutoff = datetime.now().timestamp() - (minutes * 60)
    samples = []

    for line in VITALS_LOG.read_text().strip().split("\n"):
        if not line:
            continue
        try:
            entry = json.loads(line)
            ts = datetime.fromisoformat(entry["ts"]).timestamp()
            if ts >= cutoff:
                samples.append(entry)
        except (json.JSONDecodeError, KeyError, ValueError):
            continue

    return samples


def analyze_vitals(minutes: int = 60) -> dict:
    """Analyze vitals history and return summary with spike detection.

    Returns:
    {
        "samples": 60,
        "span_minutes": 60,
        "load": {
            "current": [10.8, 14.7, 18.1],
            "peak_1m": 195.2,
            "peak_ts": "2026-03-22T23:27:20",
            "avg_1m": 15.3,
            "spikes": [{"ts": "...", "load": 195.2, "top": [...], "duration_est_min": 5}],
        },
        "thermal": {
            "current": 0,
            "peak": 2,
            "peak_ts": "...",
            "time_above_nominal_pct": 15.0,
        },
        "swap": {
            "current_mb": 1200,
            "peak_mb": 8500,
            "peak_ts": "...",
        },
        "worst_offenders": [
            {"name": "fileproviderd", "appearances": 45, "peak_cpu": 99.9},
        ]
    }
    """
    samples = read_vitals(minutes)
    if not samples:
        return {"samples": 0, "span_minutes": 0}

    cores = samples[-1].get("cores", os.cpu_count() or 8)

    # Load analysis
    loads_1m = [(s["ts"], s["load"][0]) for s in samples if "load" in s]
    peak_entry = max(loads_1m, key=lambda x: x[1]) if loads_1m else (None, 0)
    avg_1m = sum(l[1] for l in loads_1m) / len(loads_1m) if loads_1m else 0

    # Spike detection: load > 3x cores
    spike_threshold = cores * 3
    spikes = []
    in_spike = False
    spike_start = None
    spike_peak = 0
    spike_top = []

    for s in samples:
        load_1 = s.get("load", [0])[0]
        if load_1 > spike_threshold:
            if not in_spike:
                in_spike = True
                spike_start = s["ts"]
                spike_peak = load_1
                spike_top = s.get("top", [])
            else:
                if load_1 > spike_peak:
                    spike_peak = load_1
                    spike_top = s.get("top", [])
        elif in_spike:
            in_spike = False
            spikes.append({
                "start": spike_start,
                "end": s["ts"],
                "peak_load": round(spike_peak, 1),
                "top_processes": spike_top[:3],
            })
            spike_start = None

    # Close unclosed spike
    if in_spike and spike_start:
        spikes.append({
            "start": spike_start,
            "end": samples[-1]["ts"],
            "peak_load": round(spike_peak, 1),
            "top_processes": spike_top[:3],
            "ongoing": True,
        })

    # Thermal analysis
    thermal_levels = [(s["ts"], s["thermal"]) for s in samples if "thermal" in s]
    thermal_peak = max(thermal_levels, key=lambda x: x[1]) if thermal_levels else (None, 0)
    above_nominal = sum(1 for _, t in thermal_levels if t > 0)
    thermal_pct = (above_nominal / len(thermal_levels) * 100) if thermal_levels else 0

    # Swap analysis
    swaps = [(s["ts"], s["swap_mb"]) for s in samples if "swap_mb" in s]
    swap_peak = max(swaps, key=lambda x: x[1]) if swaps else (None, 0)

    # Worst offenders: per-process pressure analysis
    proc_stats: dict[str, dict] = {}
    for i, s in enumerate(samples):
        for item in s.get("top", []):
            name = item[1]
            cpu = item[0]
            if name not in proc_stats:
                proc_stats[name] = {
                    "appearances": 0, "peak_cpu": 0, "total_cpu": 0,
                    "first_seen": i, "last_seen": i, "cpu_series": [],
                }
            proc_stats[name]["appearances"] += 1
            proc_stats[name]["peak_cpu"] = max(proc_stats[name]["peak_cpu"], cpu)
            proc_stats[name]["total_cpu"] += cpu
            proc_stats[name]["last_seen"] = i
            proc_stats[name]["cpu_series"].append(cpu)

    # Compute derived metrics
    total_samples = len(samples)
    for name, stats in proc_stats.items():
        stats["avg_cpu"] = round(stats["total_cpu"] / max(stats["appearances"], 1), 1)
        stats["presence_pct"] = round(stats["appearances"] / max(total_samples, 1) * 100, 1)
        # Duration estimate: span from first to last seen
        span = stats["last_seen"] - stats["first_seen"] + 1
        stats["span_samples"] = span
        # Sustained = present in >50% of samples AND avg CPU > 5%
        stats["sustained"] = stats["presence_pct"] > 50 and stats["avg_cpu"] > 5

    # Sort by total_cpu (cumulative pressure), not just appearances
    worst = sorted(proc_stats.items(), key=lambda x: x[1]["total_cpu"], reverse=True)[:15]

    return {
        "samples": len(samples),
        "span_minutes": minutes,
        "load": {
            "current": samples[-1].get("load", []),
            "peak_1m": round(peak_entry[1], 1),
            "peak_ts": peak_entry[0],
            "avg_1m": round(avg_1m, 1),
            "spikes": spikes,
            "cores": cores,
        },
        "thermal": {
            "current": thermal_levels[-1][1] if thermal_levels else None,
            "peak": thermal_peak[1],
            "peak_ts": thermal_peak[0],
            "time_above_nominal_pct": round(thermal_pct, 1),
        },
        "swap": {
            "current_mb": swaps[-1][1] if swaps else None,
            "peak_mb": swap_peak[1] if swap_peak[0] else 0,
            "peak_ts": swap_peak[0],
        },
        "worst_offenders": [
            {"name": name, **stats} for name, stats in worst
        ],
    }


def run_monitor(interval: int = 60, once: bool = False):
    """Run the vitals monitor loop (or single sample)."""
    if once:
        s = sample()
        record(s)
        return s

    try:
        while True:
            s = sample()
            record(s)
            time.sleep(interval)
    except KeyboardInterrupt:
        pass
