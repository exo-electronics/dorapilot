#!/usr/bin/env python3
"""Vehicle parameters — platform-specific calibration constants.

Loaded at runtime; no hot-reload (restart node to apply changes).
"""
from dataclasses import dataclass


@dataclass
class VehicleParams:
    # Geometry
    wheelbase_m: float = 2.65
    track_width_m: float = 1.58
    cg_height_m: float = 0.55
    front_overhang_m: float = 0.92
    rear_overhang_m: float = 0.87

    # Steering
    steer_ratio: float = 15.4
    max_steer_angle_deg: float = 540.0
    steer_deadband_deg: float = 1.0

    # Dynamics
    mass_kg: float = 1650.0
    max_accel_mps2: float = 3.0
    max_decel_mps2: float = 9.8
    max_jerk_mps3: float = 5.0
    drag_coeff: float = 0.28

    # Limits
    max_speed_mps: float = 44.4   # 160 km/h
    engagement_min_speed_mps: float = 0.0
    engagement_max_speed_mps: float = 41.7  # 150 km/h

    # CAN interface
    can_interface: str = "can0"
    can_bitrate: int = 500_000

    @classmethod
    def from_env(cls) -> "VehicleParams":
        import os
        return cls(
            wheelbase_m=float(os.environ.get("VEHICLE_WHEELBASE_M", cls.wheelbase_m)),
            mass_kg=float(os.environ.get("VEHICLE_MASS_KG", cls.mass_kg)),
            steer_ratio=float(os.environ.get("VEHICLE_STEER_RATIO", cls.steer_ratio)),
            can_interface=os.environ.get("VEHICLE_CAN_INTERFACE", cls.can_interface),
        )


PARAMS = VehicleParams.from_env()
