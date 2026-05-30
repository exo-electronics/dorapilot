#!/usr/bin/env python3
"""Image preprocess operator — crop/resize/format convert."""
import pyarrow as pa
import numpy as np
from dora import DoraStatus
from drp_msgs import Image
from drp_msgs.utils import from_arrow, to_arrow

class Operator:
    def __init__(self):
        self.target_w = 512
        self.target_h = 256

    def on_event(self, dora_event, send_output):
        if dora_event["type"] == "INPUT":
            return self.on_input(dora_event, send_output)
        return DoraStatus.CONTINUE

    def on_input(self, dora_input, send_output):
        img = from_arrow(dora_input["value"], Image)
        img.width = self.target_w
        img.height = self.target_h
        send_output("image_resized", to_arrow(img))
        send_output("image_yuv", to_arrow(img))
        return DoraStatus.CONTINUE
