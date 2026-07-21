package aad

import (
	"encoding/json"
	"fmt"
	"math"
	"strconv"
	"strings"
	"time"
)

// ponytail: profile/context-aware fix hints and persisted history (..context/
// ..storage) deferred; fixed default thresholds ported. Also: the shared run()
// helper collapses "exec/timeout failure" and "command ran but exited nonzero"
// into the same empty-string result, whereas the Python only emits the
// "could not query" INFO finding on an actual exception (TimeoutExpired/
// OSError/ValueError) — a bare nonzero exit falls through to the generic
// "checks unavailable" finding instead. Both paths converge on an INFO
// finding either way, so verdicts are unaffected; only the wording of that
// rare edge case may differ.
func init() {
	register(Check{Name: "Network", Run: checkNetwork})
	register(Check{Name: "Network Speed", Run: checkNetworkSpeed, OptIn: true})
}

// checkNetwork checks Wi-Fi signal strength. Fast — no bandwidth test.
func checkNetwork() CheckResult {
	r := CheckResult{Name: "Network"}

	out := run("system_profiler", "SPAirPortDataType", "-json")
	if out == "" {
		r.add(Finding{Check: "network", Severity: INFO, Summary: "Wi-Fi: could not query wireless status"})
	} else {
		var data map[string]any
		if err := json.Unmarshal([]byte(out), &data); err != nil {
			r.add(Finding{Check: "network", Severity: INFO, Summary: "Wi-Fi: could not query wireless status"})
		} else {
			apList, _ := data["SPAirPortDataType"].([]any)
			var ap map[string]any
			if len(apList) > 0 {
				ap, _ = apList[0].(map[string]any)
			}
			var ifaces []any
			if ap != nil {
				ifaces, _ = ap["spairport_airport_interfaces"].([]any)
			}
			if len(ifaces) > 0 {
				iface0, _ := ifaces[0].(map[string]any)
				ci, _ := iface0["spairport_current_network_information"].(map[string]any)

				ssid, _ := ci["_name"].(string)
				channelInfo := networkStringOrDefault(ci["spairport_network_channel"], "?")
				phy, _ := ci["spairport_network_phymode"].(string)
				rssiStr, _ := ci["spairport_signal_noise"].(string)

				var rssiVal, noiseVal *int
				if rssiStr != "" && strings.Contains(rssiStr, "/") {
					parts := strings.SplitN(rssiStr, "/", 2)
					if len(parts) == 2 {
						rs := strings.TrimSpace(strings.ReplaceAll(parts[0], " dBm", ""))
						ns := strings.TrimSpace(strings.ReplaceAll(parts[1], " dBm", ""))
						rv, errR := strconv.Atoi(rs)
						nv, errN := strconv.Atoi(ns)
						if errR == nil && errN == nil {
							rssiVal, noiseVal = &rv, &nv
						}
					}
				}

				switch {
				case ssid != "" && rssiVal != nil:
					var sev Severity
					var quality string
					switch {
					case *rssiVal >= -50:
						sev, quality = OK, "excellent"
					case *rssiVal >= -60:
						sev, quality = OK, "good"
					case *rssiVal >= -70:
						sev, quality = WARNING, "fair"
					default:
						sev, quality = CRITICAL, "poor"
					}

					snr := ""
					if noiseVal != nil {
						snr = fmt.Sprintf(", SNR %d dB", *rssiVal-*noiseVal)
					}
					phyLabel := ""
					if phy != "" {
						phyLabel = " (" + phy + ")"
					}
					fix := ""
					if sev != OK {
						fix = "Move closer to router or switch to 5GHz band"
					}
					r.add(Finding{
						Check:    "network",
						Severity: sev,
						Summary:  fmt.Sprintf("Wi-Fi: %s signal (%d dBm%s) on '%s' %s%s", quality, *rssiVal, snr, ssid, channelInfo, phyLabel),
						Fix:      fix,
					})
				case ssid != "":
					r.add(Finding{
						Check:    "network",
						Severity: OK,
						Summary:  fmt.Sprintf("Wi-Fi: connected to '%s' on %s", ssid, channelInfo),
					})
				default:
					r.add(Finding{Check: "network", Severity: INFO, Summary: "Wi-Fi: not connected to any network"})
				}
			}
		}
	}

	if len(r.Findings) == 0 {
		r.add(Finding{Check: "network", Severity: INFO, Summary: "Network health checks unavailable"})
	}

	return r
}

// checkNetworkSpeed runs a networkQuality speed test. Slow (10-30s), consumes
// bandwidth. Opt-in only — not part of the default checkup.
func checkNetworkSpeed() CheckResult {
	r := CheckResult{Name: "Network Speed"}

	out := runT(30*time.Second, "networkQuality", "-s", "-c")
	if out == "" {
		r.add(Finding{Check: "network_speed", Severity: INFO, Summary: "Network speed: could not run networkQuality (requires macOS 12+)"})
	} else {
		var data map[string]any
		if err := json.Unmarshal([]byte(out), &data); err != nil {
			r.add(Finding{Check: "network_speed", Severity: INFO, Summary: "Network speed: could not parse networkQuality output"})
		} else {
			dl := networkFloat(data["dl_throughput"])
			ul := networkFloat(data["ul_throughput"])
			dlMbps := networkRound1(dl / 1_000_000)
			ulMbps := networkRound1(ul / 1_000_000)

			dlResponsiveness := networkInt(data["dl_responsiveness"])
			ulResponsiveness := networkInt(data["ul_responsiveness"])
			avgRPM := (dlResponsiveness + ulResponsiveness) / 2

			var sev Severity
			switch {
			case dlMbps < 5:
				sev = CRITICAL
			case dlMbps < 25:
				sev = WARNING
			default:
				sev = OK
			}

			var respLabel string
			switch {
			case avgRPM >= 200:
				respLabel = "high"
			case avgRPM >= 60:
				respLabel = "medium"
			default:
				respLabel = "low"
			}

			fix := ""
			if sev != OK {
				fix = "Check for bandwidth-heavy apps or switch networks"
			}

			r.add(Finding{
				Check:    "network_speed",
				Severity: sev,
				Summary:  fmt.Sprintf("Speed: %.1f Mbps down / %.1f Mbps up — responsiveness: %s (%d RPM)", dlMbps, ulMbps, respLabel, avgRPM),
				Details:  fmt.Sprintf("Download: %.1f Mbps, Upload: %.1f Mbps, Responsiveness: %d RPM", dlMbps, ulMbps, avgRPM),
				Fix:      fix,
			})
		}
	}

	if len(r.Findings) == 0 {
		r.add(Finding{Check: "network_speed", Severity: INFO, Summary: "Network speed test unavailable"})
	}

	return r
}

// networkStringOrDefault renders a JSON value (typically a string, sometimes
// a number) as a string, or def if v is nil/absent.
func networkStringOrDefault(v any, def string) string {
	if v == nil {
		return def
	}
	if s, ok := v.(string); ok {
		return s
	}
	return fmt.Sprint(v)
}

// networkFloat reads a JSON-decoded numeric field (float64) defaulting to 0.
func networkFloat(v any) float64 {
	if f, ok := v.(float64); ok {
		return f
	}
	return 0
}

// networkInt reads a JSON-decoded numeric field truncated to int, defaulting to 0.
func networkInt(v any) int {
	return int(networkFloat(v))
}

func networkRound1(f float64) float64 {
	return math.Round(f*10) / 10
}
