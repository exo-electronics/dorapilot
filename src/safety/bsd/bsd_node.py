#!/usr/bin/env python3
"""Blind Spot Detection via Hailo-15H HEF — side + rear camera YOLO inference.

Hailo-15H handles YOLO BSD model; this node receives detection results and
translates to BSE events for lane-change inhibition.

Inputs:   hailo_detections (Arrow — HEF YOLO output from inference_daemon)
          vehicle_state    (VehicleState)
Outputs:  bsd_event        (String JSON — {side: left|right, confidence: float})
"""
import json
import os
from dora import Node

from drp_msgs.vehicle_msgs import VehicleState
from drp_msgs.std_msgs import String
from drp_msgs.utils import to_arrow, from_arrow

BSD_CONFIDENCE_MIN = float(os.environ.get("BSD_CONFIDENCE_MIN", "0.6"))
BSD_ZONE_M = float(os.environ.get("BSD_ZONE_M", "5.0"))  # lateral blind zone depth


class BsdNode:
    def __init__(self):
        self.node = Node()
        self._speed_mps = 0.0

    def run(self):
        for event in self.node:
            if event["type"] != "INPUT":
                if event["type"] == "STOP":
                    break
                continue

            if event["id"] == "hailo_detections":
                self._on_detections(event)
            elif event["id"] == "vehicle_state":
                vs = from_arrow(event["value"], VehicleState)
                self._speed_mps = vs.velocity_mps

    def _on_detections(self, event):
        # Expected: Arrow array of dicts with {class, confidence, x, y, w, h, camera}
        # camera: "rear_left" | "rear_right" | "rear_center"
        detections = event["value"].to_pylist()
        for det in detections:
            if det.get("confidence", 0) < BSD_CONFIDENCE_MIN:
                continue
            camera = det.get("camera", "")
            side = "left" if "left" in camera else "right" if "right" in camera else None
            if side and det.get("class") in ("car", "truck", "motorcycle", "bicycle"):
                evt = {"side": side, "confidence": det["confidence"], "camera": camera}
                self.node.send_output("bsd_event", to_arrow(String(data=json.dumps(evt))))


if __name__ == "__main__":
    BsdNode().run()
