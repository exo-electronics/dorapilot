#!/usr/bin/env python3
"""IMU receiver node → drp_msgs/Imu."""
from dora import Node
from drp_msgs import Header, Imu
from drp_msgs.utils import to_arrow

class IMUNode:
    def __init__(self):
        self.node = Node()

    def run(self):
        for event in self.node:
            if event["type"] == "INPUT":
                imu = Imu(header=Header(frame_id="imu"))
                self.node.send_output("imu_data", to_arrow(imu))
            elif event["type"] == "STOP":
                break

if __name__ == "__main__":
    IMUNode().run()
