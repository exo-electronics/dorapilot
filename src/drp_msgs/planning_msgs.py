"""
planning_msgs — Planning message types

Dorapilot-specific messages inspired by Autoware's tier4_planning_msgs
and VisionPilot's trajectory types.
"""

from dataclasses import dataclass, field
from typing import List
import numpy as np
from .std_msgs import Header
from .geometry_msgs import Pose, Twist


class ManeuverType:
    """Maneuver type constants."""
    KEEP_LANE = "keep_lane"
    CHANGE_LANE_LEFT = "change_lane_left"
    CHANGE_LANE_RIGHT = "change_lane_right"
    FOLLOW_LEAD = "follow_lead"
    STOP = "stop"
    EMERGENCY_STOP = "emergency_stop"
    PARK = "park"


@dataclass
class ManeuverCommand:
    """Behavior planner output — high-level driving intent.

    Sent by behavior_planner node at 20Hz.

    Fields:
        header: Timestamp + frame_id
        maneuver_type: One of ManeuverType constants
        target_speed_mps: Desired speed for this maneuver
        target_lane: Target lane index (0 = ego lane, -1 = left, +1 = right)
        reason: Human-readable reason for maneuver decision
    """
    header: Header = field(default_factory=Header)
    maneuver_type: str = ManeuverType.KEEP_LANE
    target_speed_mps: np.float32 = field(default_factory=lambda: np.float32(0.0))
    target_lane: np.int32 = field(default_factory=lambda: np.int32(0))
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "header": self.header.to_dict(),
            "maneuver_type": self.maneuver_type,
            "target_speed_mps": float(self.target_speed_mps),
            "target_lane": int(self.target_lane),
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ManeuverCommand":
        return cls(
            header=Header.from_dict(d.get("header", {})),
            maneuver_type=d.get("maneuver_type", ManeuverType.KEEP_LANE),
            target_speed_mps=np.float32(d.get("target_speed_mps", 0.0)),
            target_lane=np.int32(d.get("target_lane", 0)),
            reason=d.get("reason", ""),
        )


@dataclass
class TrajectoryPoint:
    """Single point on a trajectory.

    Fields:
        pose: Position and orientation
        twist: Velocity and angular rate
        accel_mps2: Longitudinal acceleration [m/s^2]
        curvature_1pm: Path curvature [1/m]
        time_from_start_s: Time from trajectory start [s]
    """
    pose: Pose = field(default_factory=Pose)
    twist: Twist = field(default_factory=Twist)
    accel_mps2: np.float32 = field(default_factory=lambda: np.float32(0.0))
    curvature_1pm: np.float32 = field(default_factory=lambda: np.float32(0.0))
    time_from_start_s: np.float32 = field(default_factory=lambda: np.float32(0.0))

    def __post_init__(self):
        if isinstance(self.pose, dict):
            self.pose = Pose.from_dict(self.pose)
        if isinstance(self.twist, dict):
            self.twist = Twist.from_dict(self.twist)

    def to_dict(self) -> dict:
        return {
            "pose": self.pose.to_dict(),
            "twist": self.twist.to_dict(),
            "accel_mps2": float(self.accel_mps2),
            "curvature_1pm": float(self.curvature_1pm),
            "time_from_start_s": float(self.time_from_start_s),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TrajectoryPoint":
        return cls(
            pose=Pose.from_dict(d.get("pose", {})),
            twist=Twist.from_dict(d.get("twist", {})),
            accel_mps2=np.float32(d.get("accel_mps2", 0.0)),
            curvature_1pm=np.float32(d.get("curvature_1pm", 0.0)),
            time_from_start_s=np.float32(d.get("time_from_start_s", 0.0)),
        )


@dataclass
class Trajectory:
    """Planned trajectory from trajectory_planner.

    Sent by trajectory_planner node at 20Hz.
    Consumed by controller at 100Hz (interpolated).

    Fields:
        header: Timestamp + frame_id
        points: List of trajectory points (typically 20-50 points, 0.05-0.1s spacing)
        maneuver_type: Maneuver this trajectory fulfills
        is_emergency: True if this is an emergency trajectory
    """
    header: Header = field(default_factory=Header)
    points: List[TrajectoryPoint] = field(default_factory=list)
    maneuver_type: str = ManeuverType.KEEP_LANE
    is_emergency: bool = False

    def __post_init__(self):
        self.points = [TrajectoryPoint.from_dict(p) if isinstance(p, dict) else p for p in self.points]

    def to_dict(self) -> dict:
        return {
            "header": self.header.to_dict(),
            "points": [p.to_dict() for p in self.points],
            "maneuver_type": self.maneuver_type,
            "is_emergency": bool(self.is_emergency),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Trajectory":
        return cls(
            header=Header.from_dict(d.get("header", {})),
            points=[TrajectoryPoint.from_dict(p) for p in d.get("points", [])],
            maneuver_type=d.get("maneuver_type", ManeuverType.KEEP_LANE),
            is_emergency=d.get("is_emergency", False),
        )
