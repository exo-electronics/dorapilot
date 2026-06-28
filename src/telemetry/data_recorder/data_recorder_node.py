#!/usr/bin/env python3
"""Data recorder — saves dora events to .drec files for replay and analysis.

Inputs:   perception_context, vehicle_state, trajectory, lateral_cmd, longitudinal_cmd
          (any topic routed via dataflow)
Outputs:  (none — writes to disk)
"""
import os
import time
import json
from pathlib import Path
from dora import Node
import pyarrow as pa
import pyarrow.ipc as ipc

RECORD_DIR = os.environ.get("RECORD_DIR", "/data/records")
MAX_FILE_SIZE_MB = int(os.environ.get("MAX_FILE_SIZE_MB", "512"))
ROTATE_INTERVAL_S = int(os.environ.get("ROTATE_INTERVAL_S", "300"))  # 5 min segments


class DataRecorderNode:
    def __init__(self):
        self.node = Node()
        Path(RECORD_DIR).mkdir(parents=True, exist_ok=True)
        self._writer = None
        self._current_file = None
        self._file_start = 0.0
        self._open_new_file()

    def _open_new_file(self):
        if self._writer:
            try:
                self._writer.close()
            except Exception:
                pass
        ts = int(time.time())
        self._current_file = os.path.join(RECORD_DIR, f"drive_{ts}.drec")
        schema = pa.schema([
            pa.field("topic", pa.string()),
            pa.field("timestamp_ns", pa.int64()),
            pa.field("data", pa.binary()),
        ])
        sink = pa.OSFile(self._current_file, "wb")
        self._writer = ipc.new_file(sink, schema)
        self._file_start = time.time()
        print(f"[data_recorder] Recording to {self._current_file}")

    def run(self):
        for event in self.node:
            if event["type"] == "INPUT":
                self._record(event)
                if time.time() - self._file_start > ROTATE_INTERVAL_S:
                    self._open_new_file()
            elif event["type"] == "STOP":
                self._close()
                break

    def _record(self, event):
        try:
            batch = pa.record_batch({
                "topic": pa.array([event["id"]]),
                "timestamp_ns": pa.array([int(time.time_ns())]),
                "data": pa.array([event["value"].to_pybytes() if hasattr(event["value"], "to_pybytes") else b""]),
            })
            self._writer.write_batch(batch)
        except Exception:
            pass

    def _close(self):
        if self._writer:
            try:
                self._writer.close()
            except Exception:
                pass


if __name__ == "__main__":
    DataRecorderNode().run()
