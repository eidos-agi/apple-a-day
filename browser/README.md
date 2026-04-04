# apple-a-day Browser Extension

Chrome extension that tracks tab lifecycle events and feeds them into apple-a-day's diagnostic pipeline.

## What it does

- Logs tab open, close, navigate, and focus events
- Takes periodic snapshots of all open tabs (every 5 minutes)
- Shows open tab count as a badge (color-coded: green < 25, yellow < 50, red 50+)
- Popup with stats: tab count, window count, tabs opened today, oldest tab
- Generates a salted instance GUID per install for multi-browser/multi-machine tracking

## Architecture

```
Chrome Extension (Manifest V3)
  background.js          Service worker — captures events, manages snapshots
  popup.html/js/css      Stats UI
      │
      ├── chrome.storage.local    Ring buffer (last 1000 events)
      │
      └── Native Messaging ──►  aad_browser_host.py ──►  browser.ndjson
                                   (stdin/stdout)        (~/.config/eidos/aad-logs/)
```

The extension buffers events locally and sends them to a native messaging host that writes NDJSON to disk. The popup works even without the native host installed.

## Setup

### 1. Load the extension

1. Open Chrome and go to `chrome://extensions`
2. Enable **Developer mode** (toggle in top right)
3. Click **Load unpacked**
4. Select this `browser/` directory

The extension ID is deterministic (set by the `key` in manifest.json): `gbfkgnkmnohlnokcmjjhhbbmofggpikc`

### 2. Install the native messaging host

```bash
aad browser install
```

This copies the host script to `~/.config/eidos/aad-browser-host/` and registers it with Chrome.

### 3. Verify

```bash
aad browser status
```

Then open/close some tabs and check the log:

```bash
tail -f ~/.config/eidos/aad-logs/browser.ndjson
```

## Data format

All records are NDJSON (one JSON object per line) in `~/.config/eidos/aad-logs/browser.ndjson`.

### Tab event

```json
{"ts":"2026-04-01T14:30:22","type":"tab_event","event":"open","tab_id":123,"window_id":1,"url":"...","title":"...","instance_id":"a3f8b2c1..."}
```

Events: `open`, `close`, `navigate`, `focus`

### Snapshot

```json
{"ts":"2026-04-01T14:30:00","type":"snapshot","tab_count":47,"window_count":3,"tabs":[{"id":123,"url":"...","title":"...","active":true,"age_min":1440}]}
```

Snapshots fire every 5 minutes via `chrome.alarms`.

## Uninstall

```bash
aad browser uninstall
```

Then remove the extension from `chrome://extensions`.

## Native host details

The native messaging host (`native-host/aad_browser_host.py`) is a zero-dependency Python script that:

- Reads Chrome's native messaging protocol (4-byte length prefix + JSON)
- Appends each message as an NDJSON line
- Rotates the log at 5 MB
- Responds to `ping` messages for health checks

## Permissions

| Permission | Why |
|-----------|-----|
| `tabs` | Read tab URLs, titles, and lifecycle events |
| `storage` | Buffer events locally, persist tab creation times and instance ID |
| `alarms` | Periodic snapshot timer |
| `nativeMessaging` | Send events to the local NDJSON writer |
