#!/usr/bin/env python3
"""lane_detector node — placeholder."""
from dora import Node

class Lane_detectorNode:
    def __init__(self):
        self.node = Node()

    def run(self):
        for event in self.node:
            if event["type"] == "INPUT":
                pass
            elif event["type"] == "STOP":
                break

if __name__ == "__main__":
    Lane_detectorNode().run()
