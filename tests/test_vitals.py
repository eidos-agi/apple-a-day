"""Tests for vitals sampling and NDJSON reading."""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from apple_a_day.vitals import read_vitals


class TestReadVitals:
    def _write_samples(self, log_file: Path, count: int, interval_sec: int = 60):
        """Write synthetic vitals samples."""
        now = datetime.now()
        with open(log_file, "w") as f:
            for i in range(count):
                ts = now - timedelta(seconds=(count - i) * interval_sec)
                entry = {
                    "ts": ts.isoformat(timespec="seconds"),
                    "load": [1.0, 1.0, 1.0],
                    "cores": 8,
                    "thermal": 0,
                    "swap_mb": 100,
                }
                f.write(json.dumps(entry, separators=(",", ":")) + "\n")

    def test_reads_recent_samples(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "vitals.ndjson"
            self._write_samples(log_file, count=100, interval_sec=60)

            with patch("apple_a_day.vitals.VITALS_LOG", log_file):
                samples = read_vitals(minutes=30)
                assert len(samples) > 0
                assert len(samples) <= 30  # ~30 samples at 1/min

    def test_empty_file_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "vitals.ndjson"
            log_file.write_text("")

            with patch("apple_a_day.vitals.VITALS_LOG", log_file):
                assert read_vitals(minutes=60) == []

    def test_missing_file_returns_empty(self):
        with patch("apple_a_day.vitals.VITALS_LOG", Path("/nonexistent/vitals.ndjson")):
            assert read_vitals(minutes=60) == []

    def test_all_old_samples_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "vitals.ndjson"
            # Write samples from 2 hours ago
            now = datetime.now()
            with open(log_file, "w") as f:
                for i in range(10):
                    ts = now - timedelta(hours=2, minutes=i)
                    entry = {"ts": ts.isoformat(timespec="seconds"), "load": [1.0, 1.0, 1.0], "cores": 8}
                    f.write(json.dumps(entry, separators=(",", ":")) + "\n")

            with patch("apple_a_day.vitals.VITALS_LOG", log_file):
                assert read_vitals(minutes=60) == []
