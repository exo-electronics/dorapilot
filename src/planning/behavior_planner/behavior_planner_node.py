#!/usr/bin/env python3
"""
Behavior planner node — Dorapilot

High-level maneuver decisions based on PerceptionContext.
Based on VisionPilot's behavior_planner + Autoware's behavior patterns.

For Autoware developers:
    Input: PerceptionContext (replaces scattered ROS2 topics)
    Output: ManeuverCommand (dorapilot-specific)
"""

import time
from dora import Node

from drp_msgs import Header, ManeuverCommand, ManeuverType, PerceptionContext
from drp_msgs.utils import to_arrow, from_arrow


class BehaviorPlannerNode:
    def __init__(self):
        self.node = Node()

    def plan(self, ctx: PerceptionContext) -> ManeuverCommand:
        """Determine maneuver from perception context."""
        header = Header(
            stamp={"sec": int(time.time()), "nanosec": 0},
            frame_id="base_link"
        )

        # Emergency stop takes priority
        if "emergency" in ctx.safety_events:
            return ManeuverCommand(
                header=header,
                maneuver_type=ManeuverType.EMERGENCY_STOP,
                target_speed_mps=0.0,
                reason="Safety event: emergency"
            )

        # Stop line detected
        if "stop_line" in ctx.safety_events:
            return ManeuverCommand(
                header=header,
                maneuver_type=ManeuverType.STOP,
                target_speed_mps=0.0,
                reason="Stop line detected"
            )

        # Pedestrian/cyclist in path
        if any(e in ctx.safety_events for e in ["pedestrian", "cyclist"]):
            return ManeuverCommand(
                header=header,
                maneuver_type=ManeuverType.STOP,
                target_speed_mps=0.0,
                reason="Vulnerable road user in path"
            )

        # Follow lead vehicle
        if ctx.lead and ctx.lead.distance_m < 50.0:
            target_speed = min(ctx.lead.velocity_mps, ctx.speed_limit_mps)
            return ManeuverCommand(
                header=header,
                maneuver_type=ManeuverType.FOLLOW_LEAD,
                target_speed_mps=target_speed,
                reason=f"Following lead at {ctx.lead.distance_m:.1f}m"
            )

        # Default: keep lane at speed limit
        return ManeuverCommand(
            header=header,
            maneuver_type=ManeuverType.KEEP_LANE,
            target_speed_mps=ctx.speed_limit_mps,
            reason="Cruise at speed limit"
        )

    def run(self):
        print("[behavior_planner] Behavior planner started")
        for event in self.node:
            if event["type"] == "INPUT":
                ctx = from_arrow(event["value"], PerceptionContext)
                cmd = self.plan(ctx)
                self.node.send_output("maneuver_command", to_arrow(cmd))
            elif event["type"] == "STOP":
                break


if __name__ == "__main__":
    node = BehaviorPlannerNode()
    node.run()
