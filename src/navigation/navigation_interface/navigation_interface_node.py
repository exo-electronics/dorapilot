#!/usr/bin/env python3
"""Navigation interface — route planning via Valhalla, feeds trajectory waypoints.

Receives intent commands (navigate_to) from voice/intent or NavPilot BLE.
Queries Valhalla for route, publishes global path to behavior_planner.

Inputs:   ui_cmd      (String JSON — navigate_to, cancel_navigation)
          pose        (PoseStamped — current position for route anchoring)
Outputs:  global_path (Path — waypoints for behavior_planner)
          nav_status  (String JSON — {active, destination, eta_s, distance_m})
"""
import json
import os
import urllib.request
from dora import Node

from drp_msgs.std_msgs import String
from drp_msgs.geometry_msgs import PoseStamped
from drp_msgs.nav_msgs import Path
from drp_msgs.utils import to_arrow, from_arrow

VALHALLA_URL = os.environ.get("VALHALLA_URL", "http://localhost:8002/route")


class NavigationInterfaceNode:
    def __init__(self):
        self.node = Node()
        self._current_pose: PoseStamped | None = None
        self._active_route = None

    def run(self):
        for event in self.node:
            if event["type"] != "INPUT":
                if event["type"] == "STOP":
                    break
                continue

            if event["id"] == "ui_cmd":
                self._on_cmd(event)
            elif event["id"] == "pose":
                self._current_pose = from_arrow(event["value"], PoseStamped)

    def _on_cmd(self, event):
        cmd = json.loads(from_arrow(event["value"], String).data)
        intent = cmd.get("intent")

        if intent == "navigate_to":
            destination = cmd.get("slots", {}).get("destination", "")
            self._plan_route(destination)
        elif intent == "cancel_navigation":
            self._active_route = None
            self.node.send_output("nav_status", to_arrow(String(data=json.dumps({"active": False}))))

    def _plan_route(self, destination: str):
        # TODO: geocode destination, call Valhalla, parse turn-by-turn
        # Stub: emit empty path
        path = Path(header_frame_id="map", poses=[])
        self.node.send_output("global_path", to_arrow(path))
        status = {"active": True, "destination": destination, "eta_s": 0, "distance_m": 0}
        self.node.send_output("nav_status", to_arrow(String(data=json.dumps(status))))


if __name__ == "__main__":
    NavigationInterfaceNode().run()
