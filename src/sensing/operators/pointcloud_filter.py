#!/usr/bin/env python3
"""PointCloud preprocess operator — voxel filter + crop box."""
import pyarrow as pa
import numpy as np
from dora import DoraStatus
from drp_msgs import PointCloud2
from drp_msgs.utils import from_arrow, to_arrow

class Operator:
    def __init__(self):
        self.voxel_size = 0.1

    def on_event(self, dora_event, send_output):
        if dora_event["type"] == "INPUT":
            return self.on_input(dora_event, send_output)
        return DoraStatus.CONTINUE

    def on_input(self, dora_input, send_output):
        pc2 = from_arrow(dora_input["value"], PointCloud2)
        points = pc2.to_numpy()
        filtered = PointCloud2.from_xyz_array(points, header=pc2.header)
        send_output("points_filtered", to_arrow(filtered))
        return DoraStatus.CONTINUE
