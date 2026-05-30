#!/usr/bin/env python3
"""GNSS receiver node → drp_msgs/NavSatFix."""
from dora import Node
from drp_msgs import Header, NavSatFix, NavSatStatus
from drp_msgs.utils import to_arrow

class GNSSNode:
    def __init__(self):
        self.node = Node()

    def run(self):
        for event in self.node:
            if event["type"] == "INPUT":
                fix = NavSatFix(
                    header=Header(frame_id="gnss"),
                    status=NavSatStatus(status=0, service=1),
                    latitude=13.7563,
                    longitude=100.5018,
                    altitude=10.0
                )
                self.node.send_output("navsatfix", to_arrow(fix))
            elif event["type"] == "STOP":
                break

if __name__ == "__main__":
    GNSSNode().run()
