"""
nav_msgs — Navigation message types

ROS2-compatible naming for Autoware developers.
"""

from dataclasses import dataclass, field
from typing import List
import numpy as np
from .std_msgs import Header
from .geometry_msgs import Pose, PoseWithCovariance, Twist


@dataclass
class Path:
    """ROS2 nav_msgs/Path equivalent."""
    header: Header = field(default_factory=Header)
    poses: List["PoseStamped"] = field(default_factory=list)

    def __post_init__(self):
        from .geometry_msgs import PoseStamped
        self.poses = [PoseStamped.from_dict(p) if isinstance(p, dict) else p for p in self.poses]

    def to_dict(self) -> dict:
        return {
            "header": self.header.to_dict(),
            "poses": [p.to_dict() for p in self.poses],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Path":
        from .geometry_msgs import PoseStamped
        return cls(
            header=Header.from_dict(d.get("header", {})),
            poses=[PoseStamped.from_dict(p) for p in d.get("poses", [])],
        )


@dataclass
class Odometry:
    """ROS2 nav_msgs/Odometry equivalent."""
    header: Header = field(default_factory=Header)
    child_frame_id: str = ""
    pose: PoseWithCovariance = field(default_factory=PoseWithCovariance)
    twist: Twist = field(default_factory=Twist)

    def to_dict(self) -> dict:
        return {
            "header": self.header.to_dict(),
            "child_frame_id": self.child_frame_id,
            "pose": self.pose.to_dict(),
            "twist": self.twist.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Odometry":
        return cls(
            header=Header.from_dict(d.get("header", {})),
            child_frame_id=d.get("child_frame_id", ""),
            pose=PoseWithCovariance.from_dict(d.get("pose", {})),
            twist=Twist.from_dict(d.get("twist", {})),
        )
