## BRUTALIZATION REPORT -- apple-a-day

**27 findings. 4 brutal, 8 harsh, 9 blunt, 6 snide.**

Generated: 2026-04-01
Target: /Users/dshanklinbv/repos-eidos-agi/apple-a-day
Focus: all (CODE, UX, RELIABILITY, PRODUCT, OPERABILITY)

---

### BRUTAL (fix today)

BRUTAL-001 [BRUTAL] apple_a_day/checks/network.py:97 -- networkQuality runs on every checkup, blocking for 10-30 seconds
  `networkQuality -s -c` is a bandwidth test that downloads and uploads data. It has a 30-second timeout. On slow connections it dominates the entire checkup duration. On metered/cellular connections it consumes real bandwidth the user is paying for. On captive portals or VPNs it hangs. This runs inside ThreadPoolExecutor in parallel with other checks, but the thread is occupied the entire time, and total checkup duration is gated by the slowest check. Users running `aad checkup` expect seconds, not 30+ seconds of waiting on a speed test they didn't ask for.
  FIX: Make network speed test opt-in. Add a `--skip-speedtest` flag (defaulting to skip), or split into `check_network_wifi()` (fast, always runs) and `check_network_speed()` (slow, opt-in). At minimum, reduce the timeout from 30s to 10s.

BRUTAL-002 [BRUTAL] apple_a_day/checks/cleanup.py:188 -- _find_stale_apps walks every file in every app bundle recursively
  `_find_stale_apps()` calls `Path(app_path).rglob("*")` to compute `size_bytes` for every non-safe app in /Applications. A typical /Applications has 50-100 apps, each with thousands of files. This is an O(millions) filesystem walk that can take 30-60 seconds. It runs inside the ThreadPoolExecutor alongside fast checks, but it dominates wall-clock time. The size data is only used for display in the `score` field -- not for severity thresholds.
  FIX: Replace `rglob("*")` with `subprocess.run(["du", "-sk", app_path])` which is orders of magnitude faster. Or just drop app size from the scoring entirely -- staleness + agent presence is sufficient signal.

BRUTAL-003 [BRUTAL] apple_a_day/vitals.py:220 -- read_vitals reads the entire vitals.ndjson into memory
  `read_vitals()` calls `VITALS_LOG.read_text().strip().split("\n")` which loads the entire file (up to 5 MB) into memory, splits it into lines, then iterates every line parsing JSON and checking timestamps. With 25 days of samples (~36,000 lines), this means parsing 36,000 JSON objects to find the last 60 minutes (~60 entries). This is called by `analyze_vitals()` which is called by both `aad report` and `aad vitals`.
  FIX: Read the file backwards (seek to end, read chunks backwards) and stop once you've passed the cutoff timestamp. Or maintain a separate index/pointer for the last N minutes. At minimum, read line-by-line instead of slurping the whole file.

BRUTAL-004 [BRUTAL] apple_a_day/runner.py:97 -- ThreadPoolExecutor spawns one thread per check (13 threads)
  `max_workers=len(ALL_CHECKS)` creates 13 threads. Most checks shell out to subprocess, so each thread is blocked on I/O. But `cleanup.py` does heavy filesystem traversal, `network.py` blocks for 30s on networkQuality, and `homebrew.py` can block for 60s on `brew doctor`. The result: 13 threads, most blocked, some hammering the filesystem in parallel with each other, and the system being diagnosed is itself under load from the diagnosis. On an already-struggling Mac, this makes things worse.
  FIX: Cap `max_workers` at 4-6. Group fast checks (sysctl-based: thermal, cpu_load, memory_pressure) together and slow checks (network, homebrew, cleanup) separately. Or use a semaphore to limit concurrent subprocess calls.

### HARSH (fix this week)

BRUTAL-005 [HARSH] apple_a_day/log.py:80 -- Score matrix has "cpu" and "thermal" dimensions but cli.py:121 only shows 7 of 9
  `log.py` computes a 9-dimension matrix (stability, cpu, thermal, memory, storage, services, security, infra, network). The `_cmd_score()` in `cli.py` only displays 7 dimensions in `dim_labels` -- it omits `cpu` and `thermal`. So the user sees a score influenced by dimensions they can't see. The HTML report and `aad report` use their own `_compute_matrix()` which has all 9. The same matrix is computed independently in two places (`log.py:81-126` and `report.py:134-194`) with identical logic but no shared function.
  FIX: Extract the matrix computation into a shared function in `log.py` or `models.py`. Fix `cli.py` `_cmd_score()` to display all 9 dimensions.

BRUTAL-006 [HARSH] apple_a_day/checks/security.py:111 -- XProtect check calls system_profiler SPInstallHistoryDataType which is extremely slow
  `system_profiler SPInstallHistoryDataType -json` dumps the entire installation history of the Mac as JSON. On a machine with years of software updates, this can take 10-15 seconds and produce megabytes of output. The check only needs XProtect entries. There is no flag to filter by name. This runs in the ThreadPoolExecutor, blocking a thread for 15 seconds.
  FIX: Check XProtect version via `/Library/Apple/System/Library/CoreServices/XProtect.bundle/Contents/version.plist` directly (instant file read). Or check `softwareupdate --history` which is faster. Remove the system_profiler call entirely.

BRUTAL-007 [HARSH] apple_a_day/report_html.py -- HTML report inlines massive SVG and has no Jinja2 template error handling
  `report_html.py` imports `jinja2` at module level. If the user installed `apple-a-day` without the `[report]` extra, `aad report --html` crashes with an unhelpful `ModuleNotFoundError: No module named 'jinja2'` traceback. The import is not wrapped in try/except with a user-friendly message. Additionally, the HTML report generates SVG inline (donut charts, sparklines, bar charts) using string concatenation in Python -- no XSS sanitization of data values that flow into SVG attributes.
  FIX: Wrap the jinja2 import in a try/except that prints "Install the report extra: pip install apple-a-day[report]". SVG: ensure all numeric values passed to SVG attributes are actually numeric (they are from internal data, but defense-in-depth).

BRUTAL-008 [HARSH] apple_a_day/profile.py:31 -- Shell history file read as binary, 50K lines, no size cap
  `_count_history_commands()` reads the last 50,000 lines of `~/.zsh_history` as raw bytes. On power users with years of history, this file can be 50-100 MB. The function reads the entire file via `f.readlines()` (loads all into memory), then slices the last 50K. For a 100 MB file, this allocates ~100 MB of memory just to count command frequencies.
  FIX: Seek to the end of the file and read backwards to collect the last 50K lines without loading the entire file. Or use `tail -50000` subprocess call.

BRUTAL-009 [HARSH] tests/ -- Test suite is skeletal: 2 test files, 3 test functions, zero mocking
  `test_checks.py` parametrizes all 13 checks and just asserts they return a CheckResult without crashing. `test_models.py` has 3 trivial assertions. There are zero tests for: CLI argument parsing, JSON output format, vitals sampling, log rotation, profile generation, browser host installation, launchd plist generation, score computation, report rendering. The checks are tested by running them live on the machine -- not by mocking subprocess calls. This means tests are non-deterministic, slow (they actually run networkQuality, brew doctor, etc.), and fail on non-Mac CI.
  FIX: Add subprocess mocking for each check module. Test CLI argument parsing with `main(["checkup", "--json"])`. Test log rotation by creating a file at the size limit. Test score computation with synthetic CheckResults.

BRUTAL-010 [HARSH] apple_a_day/checks/cleanup.py:71 -- cleanup check calls _find_stale_apps, _find_orphaned_agents, AND _find_crash_looping_agents in sequence
  Three heavy operations run sequentially inside the cleanup check: `_find_stale_apps()` walks every app bundle, `_find_orphaned_agents()` reads every plist in LaunchAgents, and `_find_crash_looping_agents()` calls `launchctl list` and reads plists again. The crash-looping detection overlaps significantly with `check_launch_agents()` in `launch_agents.py` -- both parse `launchctl list` output and both read KeepAlive from plists. Duplicate work, duplicate subprocess calls.
  FIX: Share the launchctl + plist data between `launch_agents.py` and `cleanup.py` via a shared cache or by merging the crash-loop detection. Run the three cleanup sub-operations in parallel within the check.

BRUTAL-011 [HARSH] apple_a_day/feature_extraction.py:147 -- get_brew_description shells out to `brew info --cask` per app
  When computing app similarity for the HTML report, `get_brew_description()` runs `brew info --cask --json=v2 <token>` for each stale app. With 20 stale apps, that's 20 sequential subprocess calls to brew, each with a 10s timeout. This can add 30-60 seconds to the HTML report generation on top of the checkup itself.
  FIX: Batch the brew info calls: `brew info --cask --json=v2 app1 app2 app3 ...` in a single call. Or cache the results to `~/.config/eidos/brew-cache.json` and refresh daily.

BRUTAL-012 [HARSH] apple_a_day/launchd.py:79 -- PATH environment variable in generated plist is the current shell's PATH
  `generate_plist()` embeds `os.environ.get("PATH", ...)` into the launchd plist. This captures whatever PATH was active when `aad install` was run (e.g., including pyenv shims, nvm paths, conda paths). If the user's shell environment changes (new Python version, new node version), the daemon may break because it's using a stale PATH. Worse, if installed from a virtualenv, the PATH may include the venv's bin directory which won't exist on reboot.
  FIX: Use a minimal, stable PATH in the plist: `/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin`. Or resolve the absolute path to the `aad` binary at install time and don't rely on PATH at all.

### BLUNT (fix when in the area)

BRUTAL-013 [BLUNT] apple_a_day/cli.py:492 -- Running `aad` with no arguments silently defaults to checkup instead of showing help
  When `args.command is None`, the code manually sets `args.command = "checkup"` and fills in default values. This means a user who types just `aad` expecting help gets a full checkup (which can take 30+ seconds due to networkQuality). Standard CLI convention is to show `--help` when no subcommand is given.
  FIX: Change the default behavior to `parser.print_help()` when no subcommand is given. Users who want the checkup will type `aad checkup`.

BRUTAL-014 [BLUNT] apple_a_day/models.py:70 -- worst_severity uses list(Severity).index() which depends on enum declaration order
  `max(self.findings, key=lambda f: list(Severity).index(f.severity)).severity` -- this works because Severity is declared in order OK, INFO, WARNING, CRITICAL. But it's fragile. If someone reorders the enum or adds a new severity level between existing ones, the ordering breaks silently.
  FIX: Give each Severity a numeric weight: `OK = ("ok", 0)`, `INFO = ("info", 1)`, etc. Use the weight for comparison.

BRUTAL-015 [BLUNT] browser/background.js:88 -- sendToNativeHost fires and forgets with no retry or backoff
  `sendToNativeHost()` calls `chrome.runtime.sendNativeMessage()` and silently drops failures. If the native host is not installed, every tab event generates a failed native message call. With heavy tab usage (50+ tabs, frequent navigation), this means hundreds of failed calls per hour. Chrome may rate-limit or log warnings.
  FIX: After the first failure, set a flag and stop trying for 5 minutes. Or check host availability on startup and only send if connected.

BRUTAL-016 [BLUNT] apple_a_day/checks/homebrew.py:27 -- `brew doctor` has a 60-second timeout, runs in the thread pool
  `brew doctor` runs arbitrary health checks against the Homebrew installation. It can be very slow on machines with many packages. With a 60-second timeout and no way to skip it, a slow brew doctor can make the entire checkup take over a minute. Combined with BRUTAL-001 (networkQuality), a checkup can take 90+ seconds.
  FIX: Reduce timeout to 15s. Or make homebrew check opt-in for the full checkup and only run it on `aad checkup -c homebrew`.

BRUTAL-017 [BLUNT] apple_a_day/vitals.py:183 -- swap parsing assumes "M" suffix, will break on GB-scale swap
  `used_str.rstrip("M")` assumes swap is reported in megabytes. On a machine with 100+ GB of swap (possible with heavy workloads on large-RAM machines), sysctl may report in GB format. The code will either fail to parse or report a wildly wrong number.
  FIX: Handle both "M" and "G" suffixes. Parse the full `vm.swapusage` output properly (it includes "total", "used", "free" with units).

BRUTAL-018 [BLUNT] apple_a_day/checks/kernel_panics.py:55 -- Panic file JSON parsing assumes specific format, fails silently on newer formats
  The parser tries `json.loads(lines[1])` then `json.loads(lines[0])`. macOS panic files have evolved across versions. On some macOS versions, the panic file is a single JSON object; on others, it has a text preamble. The current code catches `json.JSONDecodeError` and reports "Unparseable panic report" which loses the valuable panic data. A user with actual kernel panics gets a WARNING instead of CRITICAL with no actionable info.
  FIX: Try multiple parse strategies: full file as JSON, skip first N lines, regex for panicString. At minimum, extract the panic date and type from the filename even when parsing fails.

BRUTAL-019 [BLUNT] apple_a_day/report.py -- _render_ansi uses ANSI codes unconditionally, no TTY detection
  `report.py` defines ANSI color codes at module level and uses them in `_c()` and `_render_ansi()`. Unlike `format_ansi.py` which checks `_supports_color()` via `sys.stdout.isatty()`, `report.py` never checks. Piping `aad report` to a file or into another program produces escape-code garbage.
  FIX: Add TTY detection like `format_ansi.py` does. Or reuse the `_supports_color()` function from `format_ansi.py`.

BRUTAL-020 [BLUNT] apple_a_day/profile.py:296 -- Profile refresh threshold is 90 days, docstring says 7 days
  `get_or_create_profile()` docstring says "Refreshes if older than 7 days" but the code checks `if age_days < 90`. A user's dev tools and workspace can change significantly in 90 days. The profile drives severity adjustments and fix suggestions in checks via `context.py`. A 90-day-old profile may tell the user Docker-specific advice when they uninstalled Docker 2 months ago.
  FIX: Change threshold to 7-14 days as the docstring promises. Or make it configurable.

BRUTAL-021 [BLUNT] apple_a_day/ensemble_similarity.py -- ensemble_score is defined but never called from any code path
  `ensemble_similarity.py` defines `ensemble_score()` which is a more sophisticated version of `app_similarity.py:similarity_score()`. But `report_html.py` imports `find_redundant_apps` from `app_similarity.py`, which uses the older `similarity_score()`. The ensemble scorer is dead code -- it was built but never wired in.
  FIX: Wire `ensemble_score` into `find_redundant_apps` as the scoring function, or delete the file. Dead code rots.

### SNIDE (batch with other work)

BRUTAL-022 [SNIDE] apple_a_day/replacement_detection.py -- replacement_detection.py is dead code, imported nowhere
  `replacement_detection.py` defines `find_replacements()` and `get_app_usage()` with sophisticated temporal analysis. No file in the codebase imports it. It has no test. It's 317 lines of unused code.
  FIX: Wire it into the HTML report's cleanup section, or delete it.

BRUTAL-023 [SNIDE] apple_a_day/cli.py:479 -- browser subcommand has no handler for missing browser_action
  If user runs `aad browser` without a subaction (install/uninstall/status), `args.browser_action` is `None`. The `_cmd_browser()` function silently does nothing -- no error, no help message. Same for `args.command` resolution -- browser is handled but browser with no action is a silent no-op.
  FIX: Add `if args.browser_action is None: parser.print_help(); return`.

BRUTAL-024 [SNIDE] apple_a_day/app_similarity.py:230 -- "Microsoft Teams" appears in two synonym groups (chat AND video conferencing)
  `_SYNONYM_GROUPS` contains "Microsoft Teams" in both the chat group and the video conferencing group. The `_known_synonym_score` function iterates all groups and returns 1.0 on first match. Depending on match order, Teams may match against chat apps or video apps, but not both -- leading to inconsistent similarity results.
  FIX: Either keep Teams in one group (chat) or restructure to support multi-group membership.

BRUTAL-025 [SNIDE] pyproject.toml:47 -- MCP server entry point is commented out
  The `[project.entry-points."mcp.servers"]` section is commented out. The `mcp` optional dependency is declared. The README roadmap lists "MCP server" as a TODO. But there's no `mcp_server.py` file anywhere. The commented-out entry point is misleading.
  FIX: Remove the commented-out entry point until the MCP server is actually implemented.

BRUTAL-026 [SNIDE] apple_a_day/checks/disk_health.py:103 -- APFS container listing creates a list comprehension and discards it
  Line 103: `[v.get("Roles", []) for v in volumes]` -- this list comprehension creates a list of role arrays and immediately discards the result. It was probably intended to check for something (e.g., count roles, detect Recovery volumes) but was left as dead computation.
  FIX: Remove the dead list comprehension, or use the role data for something (e.g., report which volumes are Data vs System vs Recovery).

BRUTAL-027 [SNIDE] apple_a_day/format_rich.py -- Rich formatter doesn't show details or fix text for findings at all in some cases
  The Rich `render_report` puts `f.fix` in a separate column, but when the terminal is narrow, Rich truncates the fix column entirely. The ANSI formatter wraps fix text on separate lines with arrow prefixes. The Rich formatter provides a worse experience on narrow terminals than the zero-dependency fallback.
  FIX: Match the ANSI formatter's approach: put details and fix on separate lines below the finding instead of in a separate column.

---

### Suspicious (LOW confidence -- verify before acting)

- apple_a_day/vitals.py:183 -- swap_mb parsing: the `used_str.rstrip("M")` may also fail if sysctl output format varies across macOS versions (Ventura vs Sonoma vs Sequoia). Needs testing on multiple OS versions.
- apple_a_day/checks/thermal.py:161 -- `powermetrics` requires root. The check tries it anyway and catches PermissionError, but on some macOS versions it may prompt for password or produce a confusing error in logs.
- browser/native-host/aad_browser_host.py:54 -- The native host runs in an infinite loop with no signal handling. If Chrome kills the process, the current NDJSON write may be interrupted mid-line, corrupting the log file's last line.
- apple_a_day/profile.py:131 -- `_detect_workspace_shape()` hardcodes specific directory names (`repos`, `repos-eidos-agi`, `repos-aic`). These are the author's personal directory names, not generic user paths.
