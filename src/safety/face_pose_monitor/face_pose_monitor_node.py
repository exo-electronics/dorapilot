#!/usr/bin/env python3
"""Driver Monitoring System — face pose + gaze via Hailo-15H HEF.

face_pose_monitor.hef runs on Hailo-15H; this node interprets output.

Inputs:   hailo_dms_output (Arrow — face pose estimation from Hailo-15H)
Outputs:  dms_event        (String JSON — {alert: distracted|drowsy|absent, confidence})
          driver_attention (Bool — True=attentive)
"""
import json
import os
import time
from dora import Node

from drp_msgs.std_msgs import String, Bool
from drp_msgs.utils import to_arrow

DISTRACTION_THRESHOLD_S = float(os.environ.get("DMS_DISTRACTION_THRESHOLD_S", "2.0"))
PITCH_THRESHOLD_DEG = float(os.environ.get("DMS_PITCH_THRESHOLD_DEG", "20.0"))
YAW_THRESHOLD_DEG = float(os.environ.get("DMS_YAW_THRESHOLD_DEG", "30.0"))


class FacePoseMonitorNode:
    def __init__(self):
        self.node = Node()
        self._distracted_since: float | None = None
        self._attentive = True

    def run(self):
        for event in self.node:
            if event["type"] == "INPUT" and event["id"] == "hailo_dms_output":
                self._on_dms(event)
            elif event["type"] == "STOP":
                break

    def _on_dms(self, event):
        # Expected: Arrow scalar with {pitch_deg, yaw_deg, roll_deg, eyes_open, confidence}
        data = event["value"].to_pydict() if hasattr(event["value"], "to_pydict") else {}
        pitch = abs(data.get("pitch_deg", 0.0))
        yaw = abs(data.get("yaw_deg", 0.0))
        eyes_open = data.get("eyes_open", True)

        distracted = pitch > PITCH_THRESHOLD_DEG or yaw > YAW_THRESHOLD_DEG or not eyes_open

        if distracted:
            if self._distracted_since is None:
                self._distracted_since = time.time()
            elapsed = time.time() - self._distracted_since
            if elapsed > DISTRACTION_THRESHOLD_S and self._attentive:
                self._attentive = False
                alert_type = "drowsy" if not eyes_open else "distracted"
                self.node.send_output("dms_event", to_arrow(String(data=json.dumps({
                    "alert": alert_type,
                    "duration_s": elapsed,
                    "confidence": data.get("confidence", 0.0),
                }))))
                self.node.send_output("driver_attention", to_arrow(Bool(data=False)))
        else:
            self._distracted_since = None
            if not self._attentive:
                self._attentive = True
                self.node.send_output("driver_attention", to_arrow(Bool(data=True)))


if __name__ == "__main__":
    FacePoseMonitorNode().run()
