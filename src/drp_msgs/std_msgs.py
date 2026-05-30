"""
std_msgs — Standard message types

ROS2-compatible naming for Autoware developers.
All fields use numpy types for Arrow compatibility.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional
import numpy as np
import pyarrow as pa
import json


@dataclass
class Time:
    """ROS2 std_msgs/Time equivalent."""
    sec: np.int32 = field(default_factory=lambda: np.int32(0))
    nanosec: np.uint32 = field(default_factory=lambda: np.uint32(0))

    def to_dict(self) -> dict:
        return {"sec": int(self.sec), "nanosec": int(self.nanosec)}

    @classmethod
    def from_dict(cls, d: dict) -> "Time":
        return cls(sec=np.int32(d.get("sec", 0)), nanosec=np.uint32(d.get("nanosec", 0)))


@dataclass
class Header:
    """ROS2 std_msgs/Header equivalent.

    Every stamped message in dorapilot carries a Header.
    Autoware users: identical API to ROS2.
    """
    stamp: Time = field(default_factory=Time)
    frame_id: str = ""

    def to_dict(self) -> dict:
        return {"stamp": self.stamp.to_dict(), "frame_id": self.frame_id}

    @classmethod
    def from_dict(cls, d: dict) -> "Header":
        return cls(
            stamp=Time.from_dict(d.get("stamp", {})),
            frame_id=d.get("frame_id", "")
        )


@dataclass
class String:
    """ROS2 std_msgs/String equivalent."""
    data: str = ""

    def to_dict(self) -> dict:
        return {"data": self.data}

    @classmethod
    def from_dict(cls, d: dict) -> "String":
        return cls(data=d.get("data", ""))


@dataclass
class Bool:
    """ROS2 std_msgs/Bool equivalent."""
    data: bool = False

    def to_dict(self) -> dict:
        return {"data": bool(self.data)}

    @classmethod
    def from_dict(cls, d: dict) -> "Bool":
        return cls(data=d.get("data", False))


@dataclass
class Float32:
    """ROS2 std_msgs/Float32 equivalent."""
    data: np.float32 = field(default_factory=lambda: np.float32(0.0))

    def to_dict(self) -> dict:
        return {"data": float(self.data)}

    @classmethod
    def from_dict(cls, d: dict) -> "Float32":
        return cls(data=np.float32(d.get("data", 0.0)))


@dataclass
class Float64:
    """ROS2 std_msgs/Float64 equivalent."""
    data: np.float64 = field(default_factory=lambda: np.float64(0.0))

    def to_dict(self) -> dict:
        return {"data": float(self.data)}

    @classmethod
    def from_dict(cls, d: dict) -> "Float64":
        return cls(data=np.float64(d.get("data", 0.0)))


@dataclass
class Int32:
    """ROS2 std_msgs/Int32 equivalent."""
    data: np.int32 = field(default_factory=lambda: np.int32(0))

    def to_dict(self) -> dict:
        return {"data": int(self.data)}

    @classmethod
    def from_dict(cls, d: dict) -> "Int32":
        return cls(data=np.int32(d.get("data", 0)))


@dataclass
class Int64:
    """ROS2 std_msgs/Int64 equivalent."""
    data: np.int64 = field(default_factory=lambda: np.int64(0))

    def to_dict(self) -> dict:
        return {"data": int(self.data)}

    @classmethod
    def from_dict(cls, d: dict) -> "Int64":
        return cls(data=np.int64(d.get("data", 0)))


@dataclass
class UInt32:
    """ROS2 std_msgs/UInt32 equivalent."""
    data: np.uint32 = field(default_factory=lambda: np.uint32(0))

    def to_dict(self) -> dict:
        return {"data": int(self.data)}

    @classmethod
    def from_dict(cls, d: dict) -> "UInt32":
        return cls(data=np.uint32(d.get("data", 0)))


@dataclass
class UInt64:
    """ROS2 std_msgs/UInt64 equivalent."""
    data: np.uint64 = field(default_factory=lambda: np.uint64(0))

    def to_dict(self) -> dict:
        return {"data": int(self.data)}

    @classmethod
    def from_dict(cls, d: dict) -> "UInt64":
        return cls(data=np.uint64(d.get("data", 0)))
