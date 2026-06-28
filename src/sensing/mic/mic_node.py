#!/usr/bin/env python3
"""Microphone capture node — reads PCM audio from ALSA device.

Outputs:  audio_pcm  (raw PCM bytes, 16kHz mono int16)
"""
import os
import struct
from dora import Node
import pyarrow as pa

ALSA_DEVICE = os.environ.get("MIC_DEVICE", "hw:0,0")
SAMPLE_RATE = int(os.environ.get("MIC_SAMPLE_RATE", "16000"))
CHUNK_MS = int(os.environ.get("MIC_CHUNK_MS", "100"))


class MicNode:
    def __init__(self):
        self.node = Node()
        self._stream = self._open_alsa()
        self._chunk_frames = SAMPLE_RATE * CHUNK_MS // 1000

    def _open_alsa(self):
        try:
            import alsaaudio
            pcm = alsaaudio.PCM(
                type=alsaaudio.PCM_CAPTURE,
                mode=alsaaudio.PCM_NORMAL,
                device=ALSA_DEVICE,
                channels=1,
                rate=SAMPLE_RATE,
                format=alsaaudio.PCM_FORMAT_S16_LE,
                periodsize=SAMPLE_RATE * CHUNK_MS // 1000,
            )
            return pcm
        except Exception as e:
            print(f"[mic] ALSA unavailable ({e}) — stub mode")
            return None

    def run(self):
        for event in self.node:
            if event["type"] == "INPUT" and event["id"] == "tick":
                self._capture()
            elif event["type"] == "STOP":
                break

    def _capture(self):
        if self._stream is None:
            return
        try:
            length, data = self._stream.read()
            if length > 0:
                self.node.send_output("audio_pcm", pa.array(list(data), type=pa.uint8()))
        except Exception:
            pass


if __name__ == "__main__":
    MicNode().run()
