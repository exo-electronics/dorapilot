#!/usr/bin/env python3
"""MRM Emergency Stop — executes hard brake command on MRM trigger.

restart_policy: never — last line of defense.
"""
from dora import Node
import pyarrow as pa

from drp_msgs.safety_msgs import MRMManeuver
from drp_msgs.control_msgs import LongitudinalCommand
from drp_msgs.utils import to_arrow, from_arrow


class MrmEmergencyStopNode:
    def __init__(self):
        self.node = Node()

    def run(self):
        for event in self.node:
            if event["type"] == "INPUT" and event["id"] == "mrm_command":
                self._on_mrm(event)
            elif event["type"] == "STOP":
                break

    def _on_mrm(self, event):
        maneuver = from_arrow(event["value"], MRMManeuver)
        if maneuver.type in ("emergency_stop",):
            cmd = LongitudinalCommand(
                acceleration_mps2=-maneuver.decel_mps2,
                jerk_mps3=-10.0,
            )
            self.node.send_output("mrm_longitudinal_cmd", to_arrow(cmd))


if __name__ == "__main__":
    MrmEmergencyStopNode().run()
