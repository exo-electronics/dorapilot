"""
control_msgs — Control message types

Dorapilot-specific messages inspired by Autoware's tier4_vehicle_msgs.
"""

from dataclasses import dataclass, field
import numpy as np
from .std_msgs import Header


@dataclass
class LateralCommand:
    """Lateral control output.

    Sent by controller node at 100Hz.

    Fields:
        header: Timestamp + frame_id
        steering_angle_rad: Target steering angle [rad]
        steering_rate_rads: Target steering rate [rad/s]
        torque_nm: Target steering torque [Nm] (torque control mode)
        curvature_1pm: Target path curvature [1/m]
    """
    header: Header = field(default_factory=Header)
    steering_angle_rad: np.float32 = field(default_factory=lambda: np.float32(0.0))
    steering_rate_rads: np.float32 = field(default_factory=lambda: np.float32(0.0))
    torque_nm: np.float32 = field(default_factory=lambda: np.float32(0.0))
    curvature_1pm: np.float32 = field(default_factory=lambda: np.float32(0.0))

    def to_dict(self) -> dict:
        return {
            "header": self.header.to_dict(),
            "steering_angle_rad": float(self.steering_angle_rad),
            "steering_rate_rads": float(self.steering_rate_rads),
            "torque_nm": float(self.torque_nm),
            "curvature_1pm": float(self.curvature_1pm),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "LateralCommand":
        return cls(
            header=Header.from_dict(d.get("header", {})),
            steering_angle_rad=np.float32(d.get("steering_angle_rad", 0.0)),
            steering_rate_rads=np.float32(d.get("steering_rate_rads", 0.0)),
            torque_nm=np.float32(d.get("torque_nm", 0.0)),
            curvature_1pm=np.float32(d.get("curvature_1pm", 0.0)),
        )


@dataclass
class LongitudinalCommand:
    """Longitudinal control output.

    Sent by controller node at 100Hz.

    Fields:
        header: Timestamp + frame_id
        accel_mps2: Target acceleration [m/s^2]
        speed_mps: Target speed [m/s]
        jerk_mps3: Target jerk [m/s^3]
    """
    header: Header = field(default_factory=Header)
    accel_mps2: np.float32 = field(default_factory=lambda: np.float32(0.0))
    speed_mps: np.float32 = field(default_factory=lambda: np.float32(0.0))
    jerk_mps3: np.float32 = field(default_factory=lambda: np.float32(0.0))

    def to_dict(self) -> dict:
        return {
            "header": self.header.to_dict(),
            "accel_mps2": float(self.accel_mps2),
            "speed_mps": float(self.speed_mps),
            "jerk_mps3": float(self.jerk_mps3),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "LongitudinalCommand":
        return cls(
            header=Header.from_dict(d.get("header", {})),
            accel_mps2=np.float32(d.get("accel_mps2", 0.0)),
            speed_mps=np.float32(d.get("speed_mps", 0.0)),
            jerk_mps3=np.float32(d.get("jerk_mps3", 0.0)),
        )
