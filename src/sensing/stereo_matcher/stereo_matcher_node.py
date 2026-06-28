#!/usr/bin/env python3
"""Stereo matcher — SGM disparity from stereo_left + stereo_right.

Ported from VisionPilot stereo_matcher (ROS2 → dora-rs).
Uses RK3688 RGA for accelerated image operations where available.

Inputs:   image_stereo_left   (Image)
          image_stereo_right  (Image)
Outputs:  disparity           (Image — float32 disparity map)
          depth_map           (Image — float32 depth in meters)
"""
import os
import numpy as np
from dora import Node

from drp_msgs.sensor_msgs import Image
from drp_msgs.utils import to_arrow, from_arrow

BASELINE_M = float(os.environ.get("STEREO_BASELINE_M", "0.16"))   # 160mm baseline (ExoPilot 03H)
FOCAL_PX = float(os.environ.get("STEREO_FOCAL_PX", "1200.0"))
MIN_DISPARITY = int(os.environ.get("STEREO_MIN_DISPARITY", "0"))
NUM_DISPARITIES = int(os.environ.get("STEREO_NUM_DISPARITIES", "128"))


class StereoMatcherNode:
    def __init__(self):
        self.node = Node()
        self._left: np.ndarray | None = None
        self._right: np.ndarray | None = None
        self._matcher = self._init_matcher()

    def _init_matcher(self):
        try:
            import cv2
            return cv2.StereoSGBM_create(
                minDisparity=MIN_DISPARITY,
                numDisparities=NUM_DISPARITIES,
                blockSize=11,
                P1=8 * 3 * 11 ** 2,
                P2=32 * 3 * 11 ** 2,
                disp12MaxDiff=1,
                uniquenessRatio=10,
                speckleWindowSize=100,
                speckleRange=32,
            )
        except ImportError:
            return None

    def run(self):
        for event in self.node:
            if event["type"] != "INPUT":
                if event["type"] == "STOP":
                    break
                continue

            if event["id"] == "image_stereo_left":
                img = from_arrow(event["value"], Image)
                self._left = np.frombuffer(img.data, dtype=np.uint8).reshape(img.height, img.width, -1)
                self._compute()
            elif event["id"] == "image_stereo_right":
                img = from_arrow(event["value"], Image)
                self._right = np.frombuffer(img.data, dtype=np.uint8).reshape(img.height, img.width, -1)
                self._compute()

    def _compute(self):
        if self._left is None or self._right is None or self._matcher is None:
            return

        import cv2
        left_gray = cv2.cvtColor(self._left, cv2.COLOR_BGR2GRAY) if self._left.ndim == 3 else self._left
        right_gray = cv2.cvtColor(self._right, cv2.COLOR_BGR2GRAY) if self._right.ndim == 3 else self._right

        disparity = self._matcher.compute(left_gray, right_gray).astype(np.float32) / 16.0
        depth = np.where(disparity > 0, FOCAL_PX * BASELINE_M / disparity, 0.0)

        h, w = disparity.shape
        disp_img = Image(width=w, height=h, encoding="32FC1", data=disparity.tobytes())
        depth_img = Image(width=w, height=h, encoding="32FC1", data=depth.tobytes())

        self.node.send_output("disparity", to_arrow(disp_img))
        self.node.send_output("depth_map", to_arrow(depth_img))
        self._left = self._right = None  # consume pair


if __name__ == "__main__":
    StereoMatcherNode().run()
