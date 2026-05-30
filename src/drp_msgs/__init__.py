"""
drp_msgs — Dorapilot Message Definitions

Pure-Python message types modeled after Autoware/ROS2 conventions.
No IDL. No CMake. No rosidl. Just Python dataclasses + PyArrow.

For Autoware developers:
    from drp_msgs import Header, PointCloud2, PoseStamped, PerceptionContext
    
    msg = PerceptionContext(
        header=Header(frame_id="base_link"),
        engagement=True,
        lead=LeadVehicle(distance_m=45.2, velocity_mps=15.0)
    )
    
    # Send through DORA (zero-copy Arrow)
    node.send_output("context", msg.to_arrow())
    
    # Or convert to ROS2 for bridge
    ros2_dict = msg.to_ros2_msg()

Design goals:
- Familiar to Autoware/ROS2 users (same field names, same patterns)
- Zero compilation (pure Python)
- Native PyArrow serialization for DORA zero-copy
- Seamless ROS2 bridge conversion
"""

from .std_msgs import Header, Time, String, Bool, Float32, Float64, Int32, Int64, UInt32, UInt64
from .geometry_msgs import (
    Point, Quaternion, Pose, PoseStamped, PoseWithCovariance, PoseWithCovarianceStamped,
    Twist, TwistStamped, Vector3, Transform, TransformStamped
)
from .sensor_msgs import Image, PointCloud2, PointField, Imu, NavSatFix, NavSatStatus
from .nav_msgs import Path, Odometry
from .perception_msgs import (
    PerceptionContext, DetectedObject, DetectedObjectArray, LeadVehicle,
    LaneLine, LaneLineArray, TrafficLight, TrafficLightArray
)
from .planning_msgs import (
    Trajectory, TrajectoryPoint, ManeuverCommand, ManeuverType
)
from .control_msgs import LateralCommand, LongitudinalCommand
from .vehicle_msgs import VehicleState, VehicleCommand, GearShift
from .safety_msgs import EmergencyBrakeRequest, FCWEvent, MRMManeuver
from .utils import arrow_schema, to_arrow_batch, from_arrow_batch

__all__ = [
    # std_msgs
    "Header", "Time", "String", "Bool", "Float32", "Float64",
    "Int32", "Int64", "UInt32", "UInt64",
    # geometry_msgs
    "Point", "Quaternion", "Pose", "PoseStamped",
    "PoseWithCovariance", "PoseWithCovarianceStamped",
    "Twist", "TwistStamped", "Vector3", "Transform", "TransformStamped",
    # sensor_msgs
    "Image", "PointCloud2", "PointField", "Imu", "NavSatFix", "NavSatStatus",
    # nav_msgs
    "Path", "Odometry",
    # perception_msgs
    "PerceptionContext", "DetectedObject", "DetectedObjectArray",
    "LeadVehicle", "LaneLine", "LaneLineArray", "TrafficLight", "TrafficLightArray",
    # planning_msgs
    "Trajectory", "TrajectoryPoint", "ManeuverCommand", "ManeuverType",
    # control_msgs
    "LateralCommand", "LongitudinalCommand",
    # vehicle_msgs
    "VehicleState", "VehicleCommand", "GearShift",
    # safety_msgs
    "EmergencyBrakeRequest", "FCWEvent", "MRMManeuver",
    # utils
    "arrow_schema", "to_arrow_batch", "from_arrow_batch",
]

__version__ = "0.1.0"
