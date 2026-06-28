#!/usr/bin/env python3
"""GNSS Localizer — converts raw NavSatFix to local XY and map frame pose.

Inputs:   navsatfix  (NavSatFix)
Outputs:  gnss_pose  (PoseStamped in map frame)
"""
import numpy as np
from dora import Node

from drp_msgs.sensor_msgs import NavSatFix
from drp_msgs.geometry_msgs import PoseStamped, Pose, Point, Quaternion
from drp_msgs.std_msgs import Header
from drp_msgs.utils import to_arrow, from_arrow


class GnssLocalizerNode:
    def __init__(self):
        self.node = Node()
        self._origin: tuple[float, float] | None = None

    def run(self):
        for event in self.node:
            if event["type"] == "INPUT" and event["id"] == "navsatfix":
                self._on_fix(event)
            elif event["type"] == "STOP":
                break

    def _on_fix(self, event):
        fix = from_arrow(event["value"], NavSatFix)
        if self._origin is None:
            self._origin = (fix.latitude, fix.longitude)

        x, y = self._to_xy(fix.latitude, fix.longitude)
        pose = PoseStamped(
            header=Header(frame_id="map"),
            pose=Pose(
                position=Point(x=x, y=y, z=fix.altitude),
                orientation=Quaternion(w=1.0),
            ),
        )
        self.node.send_output("gnss_pose", to_arrow(pose))

    def _to_xy(self, lat: float, lon: float) -> tuple[float, float]:
        R = 6371000.0
        o_lat, o_lon = self._origin
        x = R * np.radians(lon - o_lon) * np.cos(np.radians(o_lat))
        y = R * np.radians(lat - o_lat)
        return x, y


if __name__ == "__main__":
    GnssLocalizerNode().run()
