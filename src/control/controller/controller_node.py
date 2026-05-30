#!/usr/bin/env python3
"""
Controller node — Dorapilot

100Hz PID controller for lateral/longitudinal tracking.
Based on VisionPilot's PID control + Autoware's control patterns.

For Autoware developers:
    Input: Trajectory (from planner), VehicleState (from ROS2 bridge)
    Output: LateralCommand, LongitudinalCommand
"""

import time
from dora import Node

from drp_msgs import (
    Header, Trajectory, VehicleState, LateralCommand, LongitudinalCommand
)
from drp_msgs.utils import to_arrow, from_arrow


class PIDController:
    """Simple PID controller."""
    def __init__(self, kp: float, ki: float, kd: float):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.integral = 0.0
        self.prev_error = 0.0

    def update(self, error: float, dt: float) -> float:
        self.integral += error * dt
        derivative = (error - self.prev_error) / dt if dt > 0 else 0.0
        self.prev_error = error
        return self.kp * error + self.ki * self.integral + self.kd * derivative

    def reset(self):
        self.integral = 0.0
        self.prev_error = 0.0


class ControllerNode:
    def __init__(self):
        self.node = Node()
        self.lateral_pid = PIDController(kp=0.5, ki=0.01, kd=0.1)
        self.longitudinal_pid = PIDController(kp=1.0, ki=0.05, kd=0.2)
        self.latest_trajectory = None
        self.latest_vehicle_state = None
        self.trajectory_idx = 0

    def interpolate_trajectory(self, traj: Trajectory, t: float):
        """Get target point at time t from trajectory."""
        if not traj.points:
            return None
        # Simple: return point closest to time t
        for i, pt in enumerate(traj.points):
            if pt.time_from_start_s >= t:
                return pt
        return traj.points[-1]

    def compute_control(self, traj: Trajectory, state: VehicleState) -> tuple:
        """Compute lateral and longitudinal commands."""
        target = self.interpolate_trajectory(traj, 0.1)  # 100ms lookahead
        if target is None:
            return (
                LateralCommand(header=Header(frame_id="base_link")),
                LongitudinalCommand(header=Header(frame_id="base_link"))
            )

        # Lateral: track curvature
        curvature_error = target.curvature_1pm
        steering_cmd = self.lateral_pid.update(curvature_error, 0.01)

        lateral = LateralCommand(
            header=Header(frame_id="base_link"),
            steering_angle_rad=steering_cmd,
            curvature_1pm=target.curvature_1pm
        )

        # Longitudinal: track speed
        speed_error = target.twist.linear.x - state.speed_mps
        accel_cmd = self.longitudinal_pid.update(speed_error, 0.01)

        longitudinal = LongitudinalCommand(
            header=Header(frame_id="base_link"),
            accel_mps2=accel_cmd,
            speed_mps=target.twist.linear.x
        )

        return lateral, longitudinal

    def on_input(self, event):
        input_id = event["id"]

        if input_id == "trajectory":
            self.latest_trajectory = from_arrow(event["value"], Trajectory)
        elif input_id == "vehicle_state":
            self.latest_vehicle_state = from_arrow(event["value"], VehicleState)

        if self.latest_trajectory and self.latest_vehicle_state:
            lateral, longitudinal = self.compute_control(
                self.latest_trajectory, self.latest_vehicle_state
            )
            self.node.send_output("lateral_cmd", to_arrow(lateral))
            self.node.send_output("longitudinal_cmd", to_arrow(longitudinal))

    def run(self):
        print("[controller] 100Hz controller started")
        for event in self.node:
            if event["type"] == "INPUT":
                self.on_input(event)
            elif event["type"] == "STOP":
                break


if __name__ == "__main__":
    node = ControllerNode()
    node.run()
