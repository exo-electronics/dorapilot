#!/usr/bin/env python3
"""traffic_light_detector node — placeholder."""
from dora import Node

class Traffic_light_detectorNode:
    def __init__(self):
        self.node = Node()

    def run(self):
        for event in self.node:
            if event["type"] == "INPUT":
                pass
            elif event["type"] == "STOP":
                break

if __name__ == "__main__":
    Traffic_light_detectorNode().run()
