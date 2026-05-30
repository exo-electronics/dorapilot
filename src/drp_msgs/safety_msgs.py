"""
safety_msgs — Safety message types

Dorapilot-specific messages for AEB, FCW, MRM.
"""

from dataclasses import dataclass, field
import numpy as np
from .std_msgs import Header


@dataclass
class EmergencyBrakeRequest:
    """Automatic Emergency Braking request.

    Sent by AEB node when collision is imminent.

    Fields:
        header: Timestamp + frame_id
        active: True if emergency braking is requested
        decel_mps2: Requested deceleration [m/s^2]
        reason: Human-readable reason ("pedestrian", "vehicle", "cyclist")
        ttc_s: Time to collision [s]
    """
    header: Header = field(default_factory=Header)
    active: bool = False
    decel_mps2: np.float32 = field(default_factory=lambda: np.float32(0.0))
    reason: str = ""
    ttc_s: np.float32 = field(default_factory=lambda: np.float32(0.0))

    def to_dict(self) -> dict:
        return {
            "header": self.header.to_dict(),
            "active": bool(self.active),
            "decel_mps2": float(self.decel_mps2),
            "reason": self.reason,
            "ttc_s": float(self.ttc_s),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "EmergencyBrakeRequest":
        return cls(
            header=Header.from_dict(d.get("header", {})),
            active=d.get("active", False),
            decel_mps2=np.float32(d.get("decel_mps2", 0.0)),
            reason=d.get("reason", ""),
            ttc_s=np.float32(d.get("ttc_s", 0.0)),
        )


@dataclass
class FCWEvent:
    """Forward Collision Warning event.

    Sent by FCW node when collision risk is detected but AEB not yet triggered.

    Fields:
        header: Timestamp + frame_id
        active: True if warning is active
        severity: "low", "medium", "high"
        object_type: "vehicle", "pedestrian", "cyclist"
        distance_m: Distance to object [m]
        relative_speed_mps: Relative speed to object [m/s]
    """
    header: Header = field(default_factory=Header)
    active: bool = False
    severity: str = "low"
    object_type: str = ""
    distance_m: np.float32 = field(default_factory=lambda: np.float32(0.0))
    relative_speed_mps: np.float32 = field(default_factory=lambda: np.float32(0.0))

    def to_dict(self) -> dict:
        return {
            "header": self.header.to_dict(),
            "active": bool(self.active),
            "severity": self.severity,
            "object_type": self.object_type,
            "distance_m": float(self.distance_m),
            "relative_speed_mps": float(self.relative_speed_mps),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "FCWEvent":
        return cls(
            header=Header.from_dict(d.get("header", {})),
            active=d.get("active", False),
            severity=d.get("severity", "low"),
            object_type=d.get("object_type", ""),
            distance_m=np.float32(d.get("distance_m", 0.0)),
            relative_speed_mps=np.float32(d.get("relative_speed_mps", 0.0)),
        )


@dataclass
class MRMManeuver:
    """Minimum Risk Maneuver command.

    Sent by MRM handler when system needs to safely stop.

    Fields:
        header: Timestamp + frame_id
        active: True if MRM is active
        maneuver_type: "pull_over", "stop_in_lane", "emergency_stop"
        target_speed_mps: Target speed for MRM [m/s]
        reason: Human-readable reason for MRM activation
    """
    header: Header = field(default_factory=Header)
    active: bool = False
    maneuver_type: str = "stop_in_lane"
    target_speed_mps: np.float32 = field(default_factory=lambda: np.float32(0.0))
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "header": self.header.to_dict(),
            "active": bool(self.active),
            "maneuver_type": self.maneuver_type,
            "target_speed_mps": float(self.target_speed_mps),
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MRMManeuver":
        return cls(
            header=Header.from_dict(d.get("header", {})),
            active=d.get("active", False),
            maneuver_type=d.get("maneuver_type", "stop_in_lane"),
            target_speed_mps=np.float32(d.get("target_speed_mps", 0.0)),
            reason=d.get("reason", ""),
        )
