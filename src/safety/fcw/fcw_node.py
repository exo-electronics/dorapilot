#!/usr/bin/env python3
"""Forward Collision Warning — audible/visual alert before AEB threshold.

restart_policy: never.
"""
import os
from dora import Node

from drp_msgs.perception_msgs import PerceptionContext
from drp_msgs.safety_msgs import FCWEvent
from drp_msgs.utils import to_arrow, from_arrow

FCW_TTC_WARN_S = float(os.environ.get("FCW_TTC_WARN_S", "4.0"))
FCW_TTC_URGENT_S = float(os.environ.get("FCW_TTC_URGENT_S", "2.8"))


class FcwNode:
    def __init__(self):
        self.node = Node()
        self._last_level = "none"

    def run(self):
        for event in self.node:
            if event["type"] == "INPUT" and event["id"] == "perception_context":
                self._evaluate(event)
            elif event["type"] == "STOP":
                break

    def _evaluate(self, event):
        ctx = from_arrow(event["value"], PerceptionContext)
        if not ctx.lead:
            self._last_level = "none"
            return

        rel_speed = max(0.0, ctx.lead.closing_speed_mps if hasattr(ctx.lead, "closing_speed_mps") else 0.0)
        ttc = ctx.lead.distance_m / max(rel_speed, 0.1)

        if ttc < FCW_TTC_URGENT_S:
            level = "urgent"
        elif ttc < FCW_TTC_WARN_S:
            level = "warn"
        else:
            level = "none"

        if level != self._last_level and level != "none":
            self._last_level = level
            evt = FCWEvent(level=level, ttc_s=ttc, distance_m=ctx.lead.distance_m)
            self.node.send_output("forward_collision_warning", to_arrow(evt))
        elif level == "none":
            self._last_level = "none"


if __name__ == "__main__":
    FcwNode().run()
