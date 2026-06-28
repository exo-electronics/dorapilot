#!/usr/bin/env python3
import os
from dora import Node
import pyarrow as pa
import numpy as np

from drp_msgs.std_msgs import String
from drp_msgs.utils import to_arrow


class WakeWordNode:
    """OpenWakeWord detector — listens on mic audio, emits event on trigger phrase."""

    WAKE_PHRASE = os.environ.get("WAKE_PHRASE", "hey dora")

    def __init__(self):
        self.node = Node()
        self._buffer: list[float] = []
        self._sample_rate = 16000

    def run(self):
        for event in self.node:
            if event["type"] == "INPUT" and event["id"] == "audio_pcm":
                self._on_audio(event)
            elif event["type"] == "STOP":
                break

    def _on_audio(self, event):
        samples = event["value"].to_numpy().view(np.int16).astype(np.float32) / 32768.0
        self._buffer.extend(samples.tolist())

        # Keep a rolling 1.5s window
        window = int(self._sample_rate * 1.5)
        if len(self._buffer) > window:
            self._buffer = self._buffer[-window:]

        if self._detect():
            self._buffer.clear()
            msg = String(data=self.WAKE_PHRASE)
            self.node.send_output("wake_event", to_arrow(msg))

    def _detect(self) -> bool:
        # TODO: integrate openwakeword or onnxruntime model
        return False


if __name__ == "__main__":
    WakeWordNode().run()
