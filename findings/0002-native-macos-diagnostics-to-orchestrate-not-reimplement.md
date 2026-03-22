---
id: '0002'
title: 'Native macOS diagnostics to orchestrate, not reimplement'
status: open
evidence: HIGH
sources: 1
created: '2026-03-22'
---

## Claim

Three Apple-native diagnostic tools should be wrapped/invoked by apple-a-day rather than reimplemented:

1. **Apple Diagnostics** — built-in hardware test for all modern Macs. Detects hardware faults and returns reference codes. Requires reboot to run, so apple-a-day should guide the user and interpret results after.
2. **Apple Hardware Test (legacy)** — older models' hardware test. Still relevant for some users. Download links cataloged at github.com/upekkha/AppleHardwareTest.
3. **sysdiagnose** — built-in bundle that collects logs and system state for deep debugging. Triggered via `sudo sysdiagnose` or keyboard shortcut (Ctrl+Option+Shift+Period). Produces a .tar.gz in /var/tmp. apple-a-day could trigger it and then parse the output.

These are first-class citizens we should orchestrate, not compete with.

## Supporting Evidence

> **Evidence: [HIGH]** — https://support.apple.com/en-us/102550, https://github.com/upekkha/AppleHardwareTest, https://support.kandji.io/kb/how-to-generate-a-sysdiagnose-in-macos, retrieved 2026-03-22

## Caveats

None identified yet.
