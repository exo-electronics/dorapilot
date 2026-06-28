#!/usr/bin/env python3
"""Lane Departure Warning — alerts when vehicle drifts across lane marking.

Inputs:   lane_lines  (LaneLineArray from lane_detector)
          vehicle_state (VehicleState)
Outputs:  ldw_event   (String JSON — {side: left|right, severity: warning|critical})
"""
import json
import os
from dora import Node

from drp_msgs.perception_msgs import PerceptionContext
from drp_msgs.vehicle_msgs import VehicleState
from drp_msgs.std_msgs import String
from drp_msgs.utils import to_arrow, from_arrow

LDW_MIN_SPEED_MPS = float(os.environ.get("LDW_MIN_SPEED_MPS", "8.0"))  # ~30 km/h
LDW_MARGIN_M = float(os.environ.get("LDW_MARGIN_M", "0.3"))


class LdwNode:
    def __init__(self):
        self.node = Node()
        self._speed_mps = 0.0
        self._turn_signal = "none"

    def run(self):
        for event in self.node:
            if event["type"] != "INPUT":
                if event["type"] == "STOP":
                    break
                continue

            if event["id"] == "perception_context":
                ctx = from_arrow(event["value"], PerceptionContext)
                self._check_ldw(ctx)
            elif event["id"] == "vehicle_state":
                vs = from_arrow(event["value"], VehicleState)
                self._speed_mps = vs.velocity_mps
                self._turn_signal = getattr(vs, "turn_signal", "none")

    def _check_ldw(self, ctx: PerceptionContext):
        if self._speed_mps < LDW_MIN_SPEED_MPS:
            return
        if self._turn_signal in ("left", "right"):
            return  # intentional lane change

        for lane in ctx.lane_lines.lanes if ctx.lane_lines else []:
            if not getattr(lane, "lateral_offset_m", None):
                continue
            offset = lane.lateral_offset_m
            side = lane.side  # "left" | "right"
            if abs(offset) < LDW_MARGIN_M:
                severity = "critical" if abs(offset) < LDW_MARGIN_M * 0.5 else "warning"
                self.node.send_output("ldw_event", to_arrow(String(data=json.dumps({
                    "side": side, "severity": severity, "offset_m": offset
                }))))


if __name__ == "__main__":
    LdwNode().run()
