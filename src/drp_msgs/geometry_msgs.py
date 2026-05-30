"""
geometry_msgs — Geometric message types

ROS2-compatible naming for Autoware developers.
"""

from dataclasses import dataclass, field
from typing import List, Optional
import numpy as np
from .std_msgs import Header


@dataclass
class Vector3:
    """ROS2 geometry_msgs/Vector3 equivalent."""
    x: np.float64 = field(default_factory=lambda: np.float64(0.0))
    y: np.float64 = field(default_factory=lambda: np.float64(0.0))
    z: np.float64 = field(default_factory=lambda: np.float64(0.0))

    def to_dict(self) -> dict:
        return {"x": float(self.x), "y": float(self.y), "z": float(self.z)}

    @classmethod
    def from_dict(cls, d: dict) -> "Vector3":
        return cls(
            x=np.float64(d.get("x", 0.0)),
            y=np.float64(d.get("y", 0.0)),
            z=np.float64(d.get("z", 0.0))
        )


@dataclass
class Point:
    """ROS2 geometry_msgs/Point equivalent."""
    x: np.float64 = field(default_factory=lambda: np.float64(0.0))
    y: np.float64 = field(default_factory=lambda: np.float64(0.0))
    z: np.float64 = field(default_factory=lambda: np.float64(0.0))

    def to_dict(self) -> dict:
        return {"x": float(self.x), "y": float(self.y), "z": float(self.z)}

    @classmethod
    def from_dict(cls, d: dict) -> "Point":
        return cls(
            x=np.float64(d.get("x", 0.0)),
            y=np.float64(d.get("y", 0.0)),
            z=np.float64(d.get("z", 0.0))
        )


@dataclass
class Quaternion:
    """ROS2 geometry_msgs/Quaternion equivalent."""
    x: np.float64 = field(default_factory=lambda: np.float64(0.0))
    y: np.float64 = field(default_factory=lambda: np.float64(0.0))
    z: np.float64 = field(default_factory=lambda: np.float64(0.0))
    w: np.float64 = field(default_factory=lambda: np.float64(1.0))

    def to_dict(self) -> dict:
        return {"x": float(self.x), "y": float(self.y), "z": float(self.z), "w": float(self.w)}

    @classmethod
    def from_dict(cls, d: dict) -> "Quaternion":
        return cls(
            x=np.float64(d.get("x", 0.0)),
            y=np.float64(d.get("y", 0.0)),
            z=np.float64(d.get("z", 0.0)),
            w=np.float64(d.get("w", 1.0))
        )


@dataclass
class Pose:
    """ROS2 geometry_msgs/Pose equivalent."""
    position: Point = field(default_factory=Point)
    orientation: Quaternion = field(default_factory=Quaternion)

    def to_dict(self) -> dict:
        return {"position": self.position.to_dict(), "orientation": self.orientation.to_dict()}

    @classmethod
    def from_dict(cls, d: dict) -> "Pose":
        return cls(
            position=Point.from_dict(d.get("position", {})),
            orientation=Quaternion.from_dict(d.get("orientation", {}))
        )


@dataclass
class PoseStamped:
    """ROS2 geometry_msgs/PoseStamped equivalent."""
    header: Header = field(default_factory=Header)
    pose: Pose = field(default_factory=Pose)

    def to_dict(self) -> dict:
        return {"header": self.header.to_dict(), "pose": self.pose.to_dict()}

    @classmethod
    def from_dict(cls, d: dict) -> "PoseStamped":
        return cls(
            header=Header.from_dict(d.get("header", {})),
            pose=Pose.from_dict(d.get("pose", {}))
        )


@dataclass
class PoseWithCovariance:
    """ROS2 geometry_msgs/PoseWithCovariance equivalent."""
    pose: Pose = field(default_factory=Pose)
    covariance: List[np.float64] = field(default_factory=lambda: [np.float64(0.0)] * 36)

    def to_dict(self) -> dict:
        return {"pose": self.pose.to_dict(), "covariance": [float(c) for c in self.covariance]}

    @classmethod
    def from_dict(cls, d: dict) -> "PoseWithCovariance":
        cov = d.get("covariance", [0.0] * 36)
        return cls(
            pose=Pose.from_dict(d.get("pose", {})),
            covariance=[np.float64(c) for c in cov]
        )


@dataclass
class PoseWithCovarianceStamped:
    """ROS2 geometry_msgs/PoseWithCovarianceStamped equivalent."""
    header: Header = field(default_factory=Header)
    pose: PoseWithCovariance = field(default_factory=PoseWithCovariance)

    def to_dict(self) -> dict:
        return {"header": self.header.to_dict(), "pose": self.pose.to_dict()}

    @classmethod
    def from_dict(cls, d: dict) -> "PoseWithCovarianceStamped":
        return cls(
            header=Header.from_dict(d.get("header", {})),
            pose=PoseWithCovariance.from_dict(d.get("pose", {}))
        )


@dataclass
class Twist:
    """ROS2 geometry_msgs/Twist equivalent."""
    linear: Vector3 = field(default_factory=Vector3)
    angular: Vector3 = field(default_factory=Vector3)

    def to_dict(self) -> dict:
        return {"linear": self.linear.to_dict(), "angular": self.angular.to_dict()}

    @classmethod
    def from_dict(cls, d: dict) -> "Twist":
        return cls(
            linear=Vector3.from_dict(d.get("linear", {})),
            angular=Vector3.from_dict(d.get("angular", {}))
        )


@dataclass
class TwistStamped:
    """ROS2 geometry_msgs/TwistStamped equivalent."""
    header: Header = field(default_factory=Header)
    twist: Twist = field(default_factory=Twist)

    def to_dict(self) -> dict:
        return {"header": self.header.to_dict(), "twist": self.twist.to_dict()}

    @classmethod
    def from_dict(cls, d: dict) -> "TwistStamped":
        return cls(
            header=Header.from_dict(d.get("header", {})),
            twist=Twist.from_dict(d.get("twist", {}))
        )


@dataclass
class Transform:
    """ROS2 geometry_msgs/Transform equivalent."""
    translation: Vector3 = field(default_factory=Vector3)
    rotation: Quaternion = field(default_factory=Quaternion)

    def to_dict(self) -> dict:
        return {"translation": self.translation.to_dict(), "rotation": self.rotation.to_dict()}

    @classmethod
    def from_dict(cls, d: dict) -> "Transform":
        return cls(
            translation=Vector3.from_dict(d.get("translation", {})),
            rotation=Quaternion.from_dict(d.get("rotation", {}))
        )


@dataclass
class TransformStamped:
    """ROS2 geometry_msgs/TransformStamped equivalent."""
    header: Header = field(default_factory=Header)
    child_frame_id: str = ""
    transform: Transform = field(default_factory=Transform)

    def to_dict(self) -> dict:
        return {
            "header": self.header.to_dict(),
            "child_frame_id": self.child_frame_id,
            "transform": self.transform.to_dict()
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TransformStamped":
        return cls(
            header=Header.from_dict(d.get("header", {})),
            child_frame_id=d.get("child_frame_id", ""),
            transform=Transform.from_dict(d.get("transform", {}))
        )
