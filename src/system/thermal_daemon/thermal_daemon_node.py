#!/usr/bin/env python3
"""Thermal daemon — monitors RK3688 + Hailo-15H temperatures, applies throttling.

Inputs:   tick (10s interval)
Outputs:  thermal_status (String JSON)
          throttle_request (String JSON — action: none|reduce_npu|reduce_cpu)
"""
import json
import glob
import os
from dora import Node

from drp_msgs.std_msgs import String
from drp_msgs.utils import to_arrow

THROTTLE_WARN_C = float(os.environ.get("THERMAL_WARN_C", "75.0"))
THROTTLE_CRIT_C = float(os.environ.get("THERMAL_CRIT_C", "85.0"))


class ThermalDaemonNode:
    THERMAL_ZONES = glob.glob("/sys/class/thermal/thermal_zone*/temp")

    def __init__(self):
        self.node = Node()

    def run(self):
        for event in self.node:
            if event["type"] == "INPUT" and event["id"] == "tick":
                self._check_temps()
            elif event["type"] == "STOP":
                break

    def _check_temps(self):
        temps = {}
        for zone_path in self.THERMAL_ZONES:
            zone = zone_path.split("/")[-2]
            try:
                with open(zone_path) as f:
                    temps[zone] = int(f.read().strip()) / 1000.0
            except Exception:
                pass

        max_temp = max(temps.values()) if temps else 0.0
        action = "none"
        if max_temp >= THROTTLE_CRIT_C:
            action = "reduce_npu"
        elif max_temp >= THROTTLE_WARN_C:
            action = "reduce_cpu"

        status = {"temps_c": temps, "max_c": max_temp, "action": action}
        self.node.send_output("thermal_status", to_arrow(String(data=json.dumps(status))))
        if action != "none":
            self.node.send_output("throttle_request", to_arrow(String(data=json.dumps({"action": action, "max_c": max_temp}))))


if __name__ == "__main__":
    ThermalDaemonNode().run()
