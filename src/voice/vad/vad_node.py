#!/usr/bin/env python3
import os
from dora import Node
import pyarrow as pa
import numpy as np

from drp_msgs.std_msgs import Bool
from drp_msgs.utils import to_arrow


class VadNode:
    """Voice Activity Detection — emits active/inactive based on energy threshold."""

    ENERGY_THRESHOLD = float(os.environ.get("VAD_ENERGY_THRESHOLD", "0.02"))
    SILENCE_FRAMES = int(os.environ.get("VAD_SILENCE_FRAMES", "8"))  # frames of silence before inactive

    def __init__(self):
        self.node = Node()
        self._active = False
        self._silence_count = 0

    def run(self):
        for event in self.node:
            if event["type"] == "INPUT" and event["id"] == "audio_pcm":
                self._on_audio(event)
            elif event["type"] == "STOP":
                break

    def _on_audio(self, event):
        samples = event["value"].to_numpy().view(np.int16).astype(np.float32) / 32768.0
        energy = float(np.sqrt(np.mean(samples ** 2)))

        speech_detected = energy > self.ENERGY_THRESHOLD

        if speech_detected:
            self._silence_count = 0
            if not self._active:
                self._active = True
                self.node.send_output("vad_active", to_arrow(Bool(data=True)))
        else:
            if self._active:
                self._silence_count += 1
                if self._silence_count >= self.SILENCE_FRAMES:
                    self._active = False
                    self._silence_count = 0
                    self.node.send_output("vad_active", to_arrow(Bool(data=False)))


if __name__ == "__main__":
    VadNode().run()
