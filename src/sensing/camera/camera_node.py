#!/usr/bin/env python3
"""Camera capture node — V4L2 → drp_msgs/Image."""
from dora import Node
from drp_msgs import Header, Image
from drp_msgs.utils import to_arrow
import v4l2capture
import numpy as np

class CameraNode:
    def __init__(self):
        self.node = Node()
        self.width = int(self.node.env.get("WIDTH", 1920))
        self.height = int(self.node.env.get("HEIGHT", 1080))
        self.device = self.node.env.get("CAMERA_DEVICE", "/dev/video0")
        # TODO: Initialize V4L2 capture

    def run(self):
        for event in self.node:
            if event["type"] == "INPUT":
                # TODO: Capture frame from V4L2
                # Placeholder: send dummy image
                img = Image(
                    header=Header(frame_id="camera"),
                    height=self.height,
                    width=self.width,
                    encoding="nv12",
                    data=b"\x00" * (self.width * self.height * 3 // 2)
                )
                self.node.send_output("image_raw", to_arrow(img))
            elif event["type"] == "STOP":
                break

if __name__ == "__main__":
    CameraNode().run()
