#!/usr/bin/env python3
"""trajectory_planner node — placeholder."""
from dora import Node

class Trajectory_plannerNode:
    def __init__(self):
        self.node = Node()

    def run(self):
        for event in self.node:
            if event["type"] == "INPUT":
                pass
            elif event["type"] == "STOP":
                break

if __name__ == "__main__":
    Trajectory_plannerNode().run()
