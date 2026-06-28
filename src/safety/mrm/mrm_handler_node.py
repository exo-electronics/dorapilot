#!/usr/bin/env python3
"""MRM Handler — Minimal Risk Maneuver coordinator.

Aggregates AEB, FCW, health signals and triggers appropriate MRM action.
restart_policy: never.
"""
from dora import Node
import pyarrow as pa

from drp_msgs.safety_msgs import EmergencyBrakeRequest, FCWEvent, MRMManeuver
from drp_msgs.utils import to_arrow, from_arrow

MRM_PRIORITY = {"emergency_stop": 3, "comfortable_stop": 2, "pull_over": 1}


class MrmHandlerNode:
    def __init__(self):
        self.node = Node()
        self._aeb_active = False
        self._health_ok = True

    def run(self):
        for event in self.node:
            if event["type"] != "INPUT":
                if event["type"] == "STOP":
                    break
                continue

            if event["id"] == "emergency_brake":
                self._on_aeb(event)
            elif event["id"] == "system_health":
                self._on_health(event)

    def _on_aeb(self, event):
        req = from_arrow(event["value"], EmergencyBrakeRequest)
        maneuver = MRMManeuver(
            type="emergency_stop",
            reason=req.reason,
            decel_mps2=req.decel_mps2,
        )
        self.node.send_output("mrm_command", to_arrow(maneuver))

    def _on_health(self, event):
        # TODO: parse system health and trigger comfortable_stop if critical daemon down
        pass


if __name__ == "__main__":
    MrmHandlerNode().run()
