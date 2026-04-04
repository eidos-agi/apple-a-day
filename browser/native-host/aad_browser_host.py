#!/usr/bin/env python3
"""apple-a-day browser native messaging host.

Receives JSON messages from the Chrome extension via stdin (Chrome NMH protocol)
and appends them as NDJSON lines to ~/.config/eidos/aad-logs/browser.ndjson.

Protocol: each message is a 4-byte little-endian length prefix followed by JSON.
Response: same format, {"ok": true} for each message.

Zero dependencies — stdlib only.
"""

import json
import struct
import sys
from datetime import datetime
from pathlib import Path

LOG_DIR = Path.home() / ".config" / "eidos" / "aad-logs"
BROWSER_LOG = LOG_DIR / "browser.ndjson"
MAX_LOG_SIZE = 5 * 1024 * 1024  # 5 MB, then rotate


def read_message():
    """Read one Chrome NMH message from stdin."""
    raw_length = sys.stdin.buffer.read(4)
    if not raw_length or len(raw_length) < 4:
        return None
    length = struct.unpack("<I", raw_length)[0]
    if length == 0:
        return None
    data = sys.stdin.buffer.read(length)
    return json.loads(data.decode("utf-8"))


def send_message(obj):
    """Write one Chrome NMH message to stdout."""
    encoded = json.dumps(obj, separators=(",", ":")).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("<I", len(encoded)))
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()


def rotate_if_needed():
    """Rotate log if it exceeds max size."""
    if BROWSER_LOG.exists() and BROWSER_LOG.stat().st_size > MAX_LOG_SIZE:
        rotated = LOG_DIR / f"browser-{datetime.now().strftime('%Y%m%d-%H%M%S')}.ndjson"
        BROWSER_LOG.rename(rotated)


def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    while True:
        msg = read_message()
        if msg is None:
            break

        # Handle ping (health check from popup)
        if msg.get("type") == "ping":
            send_message({"ok": True, "host": "aad-browser"})
            continue

        # Append to NDJSON log
        rotate_if_needed()
        with open(BROWSER_LOG, "a") as f:
            f.write(json.dumps(msg, separators=(",", ":")) + "\n")

        send_message({"ok": True})


if __name__ == "__main__":
    main()
