#!/usr/bin/env python3
"""lidar_detector node — placeholder."""
from dora import Node

class Lidar_detectorNode:
    def __init__(self):
        self.node = Node()

    def run(self):
        for event in self.node:
            if event["type"] == "INPUT":
                pass
            elif event["type"] == "STOP":
                break

if __name__ == "__main__":
    Lidar_detectorNode().run()
