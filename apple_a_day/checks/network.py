"""Check network health: throughput, latency, Wi-Fi signal quality."""

import subprocess

from ..models import CheckResult, Finding, Severity


def check_network() -> CheckResult:
    """Check network quality and Wi-Fi signal strength."""
    result = CheckResult(name="Network")

    # Wi-Fi signal via system_profiler (replaces deprecated airport command)
    try:
        out = subprocess.run(
            ["system_profiler", "SPAirPortDataType", "-json"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if out.returncode == 0:
            import json

            data = json.loads(out.stdout)
            ap = data.get("SPAirPortDataType", [{}])[0]
            ifaces = ap.get("spairport_airport_interfaces", [])

            if ifaces:
                ci = ifaces[0].get("spairport_current_network_information", {})
                ssid = ci.get("_name", "")
                channel_info = ci.get("spairport_network_channel", "?")
                phy = ci.get("spairport_network_phymode", "")

                # Parse RSSI from "signal / noise" format (e.g. "-53 dBm / -95 dBm")
                rssi_str = ci.get("spairport_signal_noise", "")
                rssi_val = None
                noise_val = None
                if rssi_str and "/" in rssi_str:
                    parts = rssi_str.split("/")
                    try:
                        rssi_val = int(parts[0].strip().replace(" dBm", ""))
                        noise_val = int(parts[1].strip().replace(" dBm", ""))
                    except (ValueError, IndexError):
                        pass

                if ssid and rssi_val is not None:
                    if rssi_val >= -50:
                        sev, quality = Severity.OK, "excellent"
                    elif rssi_val >= -60:
                        sev, quality = Severity.OK, "good"
                    elif rssi_val >= -70:
                        sev, quality = Severity.WARNING, "fair"
                    else:
                        sev, quality = Severity.CRITICAL, "poor"

                    snr = ""
                    if noise_val is not None:
                        snr = f", SNR {rssi_val - noise_val} dB"

                    phy_label = f" ({phy})" if phy else ""
                    result.findings.append(
                        Finding(
                            check="network",
                            severity=sev,
                            summary=f"Wi-Fi: {quality} signal ({rssi_val} dBm{snr}) on '{ssid}' {channel_info}{phy_label}",
                            fix="Move closer to router or switch to 5GHz band"
                            if sev != Severity.OK
                            else "",
                        )
                    )
                elif ssid:
                    result.findings.append(
                        Finding(
                            check="network",
                            severity=Severity.OK,
                            summary=f"Wi-Fi: connected to '{ssid}' on {channel_info}",
                        )
                    )
                else:
                    result.findings.append(
                        Finding(
                            check="network",
                            severity=Severity.INFO,
                            summary="Wi-Fi: not connected to any network",
                        )
                    )
    except (subprocess.TimeoutExpired, OSError, ValueError):
        result.findings.append(
            Finding(
                check="network",
                severity=Severity.INFO,
                summary="Wi-Fi: could not query wireless status",
            )
        )

    # networkQuality (macOS 12+)
    try:
        out = subprocess.run(
            ["networkQuality", "-s", "-c"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if out.returncode == 0:
            import json

            data = json.loads(out.stdout)

            dl = data.get("dl_throughput", 0)
            ul = data.get("ul_throughput", 0)
            # Throughput is in bits per second
            dl_mbps = round(dl / 1_000_000, 1)
            ul_mbps = round(ul / 1_000_000, 1)

            dl_responsiveness = data.get("dl_responsiveness", 0)
            ul_responsiveness = data.get("ul_responsiveness", 0)
            # Responsiveness is in RPM (round trips per minute)
            avg_rpm = (dl_responsiveness + ul_responsiveness) // 2

            if dl_mbps < 5:
                sev = Severity.CRITICAL
            elif dl_mbps < 25:
                sev = Severity.WARNING
            else:
                sev = Severity.OK

            # Responsiveness rating (Apple's scale)
            if avg_rpm >= 200:
                resp_label = "high"
            elif avg_rpm >= 60:
                resp_label = "medium"
            else:
                resp_label = "low"

            result.findings.append(
                Finding(
                    check="network",
                    severity=sev,
                    summary=f"Speed: {dl_mbps} Mbps down / {ul_mbps} Mbps up — responsiveness: {resp_label} ({avg_rpm} RPM)",
                    details=f"Download: {dl_mbps} Mbps, Upload: {ul_mbps} Mbps, Responsiveness: {avg_rpm} RPM",
                    fix="Check for bandwidth-heavy apps or switch networks"
                    if sev != Severity.OK
                    else "",
                )
            )
    except (subprocess.TimeoutExpired, OSError):
        result.findings.append(
            Finding(
                check="network",
                severity=Severity.INFO,
                summary="Network speed: could not run networkQuality (requires macOS 12+)",
            )
        )
    except (ValueError, KeyError):
        result.findings.append(
            Finding(
                check="network",
                severity=Severity.INFO,
                summary="Network speed: could not parse networkQuality output",
            )
        )

    if not result.findings:
        result.findings.append(
            Finding(
                check="network",
                severity=Severity.INFO,
                summary="Network health checks unavailable",
            )
        )

    return result
