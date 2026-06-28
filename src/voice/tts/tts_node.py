#!/usr/bin/env python3
"""TTS output router — sends text to piper_tts and queues audio playback.

Inputs:   tts_text  (String)
Outputs:  audio_out (raw PCM bytes for speaker)
"""
import subprocess
import os
from dora import Node
import pyarrow as pa

from drp_msgs.std_msgs import String
from drp_msgs.utils import from_arrow

PIPER_BIN = os.environ.get("PIPER_BIN", "/usr/local/bin/piper")
PIPER_MODEL = os.environ.get("PIPER_MODEL", "/data/models/en_US-lessac-medium.onnx")


class TtsNode:
    def __init__(self):
        self.node = Node()

    def run(self):
        for event in self.node:
            if event["type"] == "INPUT" and event["id"] == "tts_text":
                self._speak(event)
            elif event["type"] == "STOP":
                break

    def _speak(self, event):
        msg = from_arrow(event["value"], String)
        text = msg.data.strip()
        if not text:
            return

        try:
            result = subprocess.run(
                [PIPER_BIN, "--model", PIPER_MODEL, "--output_raw"],
                input=text.encode(),
                capture_output=True,
                timeout=5.0,
            )
            if result.returncode == 0:
                pcm = result.stdout
                self.node.send_output("audio_out", pa.array(list(pcm), type=pa.uint8()))
        except Exception:
            pass


if __name__ == "__main__":
    TtsNode().run()
