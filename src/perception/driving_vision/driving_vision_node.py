#!/usr/bin/env python3
"""driving_vision node — placeholder."""
from dora import Node

class Driving_visionNode:
    def __init__(self):
        self.node = Node()

    def run(self):
        for event in self.node:
            if event["type"] == "INPUT":
                pass
            elif event["type"] == "STOP":
                break

if __name__ == "__main__":
    Driving_visionNode().run()
