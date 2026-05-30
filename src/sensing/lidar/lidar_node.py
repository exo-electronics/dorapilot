#!/usr/bin/env python3
"""
LiDAR capture node — Dorapilot

Based on autoware.universe lidar driver pattern.
Captures Pandar QT64 packets and outputs PointCloud2.

For Autoware developers:
    This replaces rslidar_driver + pointcloud_preprocessor.
    Output is drp_msgs/sensor_msgs/PointCloud2 (ROS2-compatible).
"""

import socket
import struct
import numpy as np
import pyarrow as pa
from dora import Node

from drp_msgs import Header, PointCloud2, PointField
from drp_msgs.utils import to_arrow


# Pandar QT64 packet constants
PANDAR_UDP_PORT = 2368
PANDAR_BLOCKS_PER_PACKET = 10
PANDAR_POINTS_PER_BLOCK = 64
PANDAR_POINT_SIZE = 16  # x, y, z, intensity as float32


class LidarNode:
    def __init__(self):
        self.node = Node()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", PANDAR_UDP_PORT))
        self.sock.settimeout(1.0)

    def parse_packet(self, data: bytes) -> np.ndarray:
        """Parse Pandar QT64 UDP packet to Nx4 float32 array [x, y, z, intensity]."""
        # Skip header (42 bytes: Ethernet + IP + UDP headers)
        # Pandar data block starts at offset 42
        offset = 42

        points = []
        for block in range(PANDAR_BLOCKS_PER_PACKET):
            block_offset = offset + block * PANDAR_POINTS_PER_BLOCK * 4
            for point in range(PANDAR_POINTS_PER_BLOCK):
                p_offset = block_offset + point * 4
                if p_offset + 16 > len(data):
                    break
                x, y, z, intensity = struct.unpack_from("<ffff", data, p_offset)
                if x == 0.0 and y == 0.0 and z == 0.0:
                    continue
                points.append([x, y, z, intensity])

        return np.array(points, dtype=np.float32)

    def run(self):
        print("[lidar_node] Pandar QT64 capture started")
        for event in self.node:
            if event["type"] == "INPUT":
                # Timer tick triggers frame capture
                try:
                    packet_data, addr = self.sock.recvfrom(1500)
                    points = self.parse_packet(packet_data)

                    if len(points) == 0:
                        continue

                    # Build PointCloud2 message (ROS2-compatible)
                    pc2 = PointCloud2.from_xyz_array(
                        points,
                        header=Header(frame_id="pandar")
                    )

                    # Send via DORA zero-copy
                    self.node.send_output("pointcloud", to_arrow(pc2))

                except socket.timeout:
                    continue

            elif event["type"] == "STOP":
                break

        self.sock.close()


if __name__ == "__main__":
    node = LidarNode()
    node.run()
