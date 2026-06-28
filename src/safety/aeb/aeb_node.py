#!/usr/bin/env python3
"""Autonomous Emergency Braking — monitors perception context, triggers hard stop.

restart_policy: never — must survive main pipeline restart.
"""
import os
from dora import Node
import pyarrow as pa

from drp_msgs.perception_msgs import PerceptionContext
from drp_msgs.vehicle_msgs import VehicleState
from drp_msgs.safety_msgs import EmergencyBrakeRequest
from drp_msgs.utils import to_arrow, from_arrow

TTC_THRESHOLD_S = float(os.environ.get("AEB_TTC_THRESHOLD_S", "2.5"))
MIN_SPEED_MPS = float(os.environ.get("AEB_MIN_SPEED_MPS", "1.0"))


class AebNode:
    def __init__(self):
        self.node = Node()
        self._ctx: PerceptionContext | None = None
        self._speed_mps = 0.0

    def run(self):
        for event in self.node:
            if event["type"] != "INPUT":
                if event["type"] == "STOP":
                    break
                continue

            if event["id"] == "perception_context":
                self._ctx = from_arrow(event["value"], PerceptionContext)
                self._evaluate()
            elif event["id"] == "vehicle_state":
                vs = from_arrow(event["value"], VehicleState)
                self._speed_mps = vs.velocity_mps

    def _evaluate(self):
        if self._ctx is None or self._speed_mps < MIN_SPEED_MPS:
            return
        if not self._ctx.lead:
            return

        ttc = self._ctx.lead.distance_m / max(self._speed_mps - self._ctx.lead.velocity_mps, 0.1)
        if ttc < TTC_THRESHOLD_S:
            req = EmergencyBrakeRequest(
                reason="aeb_ttc",
                decel_mps2=9.0,
                source_node="aeb",
            )
            self.node.send_output("emergency_brake_request", to_arrow(req))


if __name__ == "__main__":
    AebNode().run()
