#!/usr/bin/env python3
"""Piper TTS node — synthesizes speech via piper binary, plays via ALSA.

Inputs:   tts_text  (String)
"""
import subprocess
import os
from dora import Node

from drp_msgs.std_msgs import String
from drp_msgs.utils import from_arrow

PIPER_BIN = os.environ.get("PIPER_BIN", "/usr/local/bin/piper")
PIPER_MODEL = os.environ.get("PIPER_MODEL", "/data/models/en_US-lessac-medium.onnx")
ALSA_DEVICE = os.environ.get("TTS_ALSA_DEVICE", "default")


class PiperTtsNode:
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
            piper = subprocess.Popen(
                [PIPER_BIN, "--model", PIPER_MODEL, "--output_raw"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
            )
            aplay = subprocess.Popen(
                ["aplay", "-r", "22050", "-f", "S16_LE", "-c", "1", "-D", ALSA_DEVICE],
                stdin=piper.stdout, stderr=subprocess.DEVNULL
            )
            piper.stdin.write(text.encode())
            piper.stdin.close()
            aplay.wait(timeout=10.0)
        except Exception:
            pass


if __name__ == "__main__":
    PiperTtsNode().run()
