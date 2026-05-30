"""
vehicle_msgs — Vehicle state and command message types

Dorapilot-specific messages inspired by Autoware's tier4_vehicle_msgs.
"""

from dataclasses import dataclass, field
import numpy as np
from .std_msgs import Header
from .geometry_msgs import Twist


class GearShift:
    """Gear shift constants."""
    PARK = "park"
    REVERSE = "reverse"
    NEUTRAL = "neutral"
    DRIVE = "drive"
    LOW = "low"


@dataclass
class VehicleState:
    """Current vehicle state from CAN/vehicle interface.

    Received via ROS2 bridge at 100Hz.

    Fields:
        header: Timestamp + frame_id
        speed_mps: Vehicle speed [m/s]
        steering_angle_rad: Current steering angle [rad]
        accel_mps2: Current acceleration [m/s^2]
        gear: Current gear (GearShift constant)
        left_turn_signal: Left turn signal state
        right_turn_signal: Right turn signal state
        brake_pressed: Driver brake pedal state
        throttle_pressed: Driver throttle pedal state
    """
    header: Header = field(default_factory=Header)
    speed_mps: np.float32 = field(default_factory=lambda: np.float32(0.0))
    steering_angle_rad: np.float32 = field(default_factory=lambda: np.float32(0.0))
    accel_mps2: np.float32 = field(default_factory=lambda: np.float32(0.0))
    gear: str = GearShift.PARK
    left_turn_signal: bool = False
    right_turn_signal: bool = False
    brake_pressed: bool = False
    throttle_pressed: bool = False

    def to_dict(self) -> dict:
        return {
            "header": self.header.to_dict(),
            "speed_mps": float(self.speed_mps),
            "steering_angle_rad": float(self.steering_angle_rad),
            "accel_mps2": float(self.accel_mps2),
            "gear": self.gear,
            "left_turn_signal": bool(self.left_turn_signal),
            "right_turn_signal": bool(self.right_turn_signal),
            "brake_pressed": bool(self.brake_pressed),
            "throttle_pressed": bool(self.throttle_pressed),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "VehicleState":
        return cls(
            header=Header.from_dict(d.get("header", {})),
            speed_mps=np.float32(d.get("speed_mps", 0.0)),
            steering_angle_rad=np.float32(d.get("steering_angle_rad", 0.0)),
            accel_mps2=np.float32(d.get("accel_mps2", 0.0)),
            gear=d.get("gear", GearShift.PARK),
            left_turn_signal=d.get("left_turn_signal", False),
            right_turn_signal=d.get("right_turn_signal", False),
            brake_pressed=d.get("brake_pressed", False),
            throttle_pressed=d.get("throttle_pressed", False),
        )


@dataclass
class VehicleCommand:
    """Unified vehicle command for actuation.

    Sent to ROS2 bridge at 100Hz.
    Converted to CAN frames by ROS2 vehicle_interface node.

    Fields:
        header: Timestamp + frame_id
        lateral: Lateral control command
        longitudinal: Longitudinal control command
        gear: Target gear (GearShift constant)
        left_turn_signal: Command left turn signal
        right_turn_signal: Command right turn signal
    """
    header: Header = field(default_factory=Header)
    lateral: "LateralCommand" = field(default_factory=lambda: __import__("drp_msgs.control_msgs", fromlist=["LateralCommand"]).LateralCommand())
    longitudinal: "LongitudinalCommand" = field(default_factory=lambda: __import__("drp_msgs.control_msgs", fromlist=["LongitudinalCommand"]).LongitudinalCommand())
    gear: str = GearShift.DRIVE
    left_turn_signal: bool = False
    right_turn_signal: bool = False

    def __post_init__(self):
        from .control_msgs import LateralCommand, LongitudinalCommand
        if isinstance(self.lateral, dict):
            self.lateral = LateralCommand.from_dict(self.lateral)
        if isinstance(self.longitudinal, dict):
            self.longitudinal = LongitudinalCommand.from_dict(self.longitudinal)

    def to_dict(self) -> dict:
        return {
            "header": self.header.to_dict(),
            "lateral": self.lateral.to_dict(),
            "longitudinal": self.longitudinal.to_dict(),
            "gear": self.gear,
            "left_turn_signal": bool(self.left_turn_signal),
            "right_turn_signal": bool(self.right_turn_signal),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "VehicleCommand":
        from .control_msgs import LateralCommand, LongitudinalCommand
        return cls(
            header=Header.from_dict(d.get("header", {})),
            lateral=LateralCommand.from_dict(d.get("lateral", {})),
            longitudinal=LongitudinalCommand.from_dict(d.get("longitudinal", {})),
            gear=d.get("gear", GearShift.DRIVE),
            left_turn_signal=d.get("left_turn_signal", False),
            right_turn_signal=d.get("right_turn_signal", False),
        )
