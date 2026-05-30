#!/usr/bin/env python3
"""ROS2 bridge node — vehicle boundary."""
from dora import Node
import pyarrow as pa
from drp_msgs import Header, VehicleState, VehicleCommand
from drp_msgs.utils import to_arrow, from_arrow

class VehicleBridgeNode:
    def __init__(self):
        self.node = Node()

    def run(self):
        for event in self.node:
            if event["type"] == "INPUT":
                # Send dummy vehicle state
                state = VehicleState(
                    header=Header(frame_id="vehicle"),
                    speed_mps=15.0,
                    steering_angle_rad=0.05
                )
                self.node.send_output("vehicle_state", to_arrow(state))
            elif event["type"] == "STOP":
                break

if __name__ == "__main__":
    VehicleBridgeNode().run()
