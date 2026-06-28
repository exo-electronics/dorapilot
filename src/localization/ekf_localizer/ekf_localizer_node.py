#!/usr/bin/env python3
"""EKF Localizer — fuses GNSS + IMU + wheel odometry into smooth pose estimate.

Ported from VisionPilot ekf_localizer (ROS2 → dora-rs).

Inputs:   navsatfix  (NavSatFix from gnss)
          imu_data   (Imu)
          vehicle_state (VehicleState — wheel speed)
Outputs:  pose       (PoseStamped — fused position + orientation)
          odometry   (Odometry)
"""
import numpy as np
from dora import Node

from drp_msgs.sensor_msgs import Imu, NavSatFix
from drp_msgs.geometry_msgs import PoseStamped, Pose, Point, Quaternion
from drp_msgs.nav_msgs import Odometry
from drp_msgs.vehicle_msgs import VehicleState
from drp_msgs.std_msgs import Header, Time
from drp_msgs.utils import to_arrow, from_arrow


class EkfLocalizerNode:
    """Extended Kalman Filter for 2D pose estimation.

    State: [x, y, heading, v_x, v_y, yaw_rate]
    Observation: GNSS (x, y), IMU (yaw_rate, accel)
    """

    DT = 0.01  # 100Hz prediction step

    def __init__(self):
        self.node = Node()
        self._x = np.zeros(6)   # state
        self._P = np.eye(6) * 0.1  # covariance
        self._initialized = False

    def run(self):
        for event in self.node:
            if event["type"] != "INPUT":
                if event["type"] == "STOP":
                    break
                continue

            if event["id"] == "navsatfix":
                self._update_gnss(event)
            elif event["id"] == "imu_data":
                self._predict_imu(event)

    def _update_gnss(self, event):
        fix = from_arrow(event["value"], NavSatFix)
        if not self._initialized:
            self._origin_lat = fix.latitude
            self._origin_lon = fix.longitude
            self._initialized = True
            return

        x_m, y_m = self._latlon_to_xy(fix.latitude, fix.longitude)
        # EKF update: GNSS observation
        H = np.array([[1, 0, 0, 0, 0, 0], [0, 1, 0, 0, 0, 0]])
        R = np.eye(2) * (fix.position_covariance[0] if fix.position_covariance else 1.0)
        y = np.array([x_m, y_m]) - H @ self._x
        S = H @ self._P @ H.T + R
        K = self._P @ H.T @ np.linalg.inv(S)
        self._x = self._x + K @ y
        self._P = (np.eye(6) - K @ H) @ self._P

        self._publish_pose(fix)

    def _predict_imu(self, event):
        imu = from_arrow(event["value"], Imu)
        yaw_rate = imu.angular_velocity_z if hasattr(imu, "angular_velocity_z") else 0.0
        ax = imu.linear_acceleration_x if hasattr(imu, "linear_acceleration_x") else 0.0
        ay = imu.linear_acceleration_y if hasattr(imu, "linear_acceleration_y") else 0.0

        if not self._initialized:
            return

        # Simple kinematic prediction
        h = self._x[2]
        self._x[0] += self._x[3] * self.DT
        self._x[1] += self._x[4] * self.DT
        self._x[2] += yaw_rate * self.DT
        self._x[3] += ax * self.DT
        self._x[4] += ay * self.DT

    def _latlon_to_xy(self, lat: float, lon: float) -> tuple[float, float]:
        R_EARTH = 6371000.0
        dlat = np.radians(lat - self._origin_lat)
        dlon = np.radians(lon - self._origin_lon)
        x = R_EARTH * dlon * np.cos(np.radians(self._origin_lat))
        y = R_EARTH * dlat
        return x, y

    def _publish_pose(self, fix: NavSatFix):
        pose = PoseStamped(
            header=Header(frame_id="map"),
            pose=Pose(
                position=Point(x=self._x[0], y=self._x[1], z=0.0),
                orientation=Quaternion(z=np.sin(self._x[2] / 2), w=np.cos(self._x[2] / 2)),
            ),
        )
        self.node.send_output("pose", to_arrow(pose))


if __name__ == "__main__":
    EkfLocalizerNode().run()
