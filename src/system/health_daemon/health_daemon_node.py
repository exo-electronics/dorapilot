#!/usr/bin/env python3
"""Health daemon — aggregates node status, watchdog, pipeline latency monitoring.

Inputs:   tick (1s interval)
          node heartbeats (from key nodes)
Outputs:  health_status (String JSON — overall system health)
"""
import json
import time
from dora import Node

from drp_msgs.std_msgs import String
from drp_msgs.utils import to_arrow

HEARTBEAT_TIMEOUT_S = 3.0

CRITICAL_NODES = ["driving_vision", "driving_policy", "controller", "vehicle_bridge"]


class HealthDaemonNode:
    def __init__(self):
        self.node = Node()
        self._heartbeats: dict[str, float] = {}

    def run(self):
        for event in self.node:
            if event["type"] != "INPUT":
                if event["type"] == "STOP":
                    break
                continue

            if event["id"] == "tick":
                self._evaluate_health()
            elif event["id"].endswith("_heartbeat"):
                node_name = event["id"].replace("_heartbeat", "")
                self._heartbeats[node_name] = time.time()

    def _evaluate_health(self):
        now = time.time()
        stale = [n for n in CRITICAL_NODES
                 if now - self._heartbeats.get(n, 0) > HEARTBEAT_TIMEOUT_S]

        healthy = len(stale) == 0
        status = {
            "healthy": healthy,
            "stale_nodes": stale,
            "timestamp": now,
        }
        self.node.send_output("health_status", to_arrow(String(data=json.dumps(status))))


if __name__ == "__main__":
    HealthDaemonNode().run()
