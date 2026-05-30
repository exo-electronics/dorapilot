"""
sensor_msgs — Sensor message types

ROS2-compatible naming for Autoware developers.
Optimized for zero-copy with PyArrow.
"""

from dataclasses import dataclass, field
from typing import List, Optional
import numpy as np
from .std_msgs import Header
from .geometry_msgs import Quaternion


@dataclass
class Image:
    """ROS2 sensor_msgs/Image equivalent.

    For zero-copy, image data is stored as raw bytes.
    Use np.frombuffer(msg.data, dtype=np.uint8).reshape(h, w, c) to decode.
    """
    header: Header = field(default_factory=Header)
    height: np.uint32 = field(default_factory=lambda: np.uint32(0))
    width: np.uint32 = field(default_factory=lambda: np.uint32(0))
    encoding: str = "rgb8"
    is_bigendian: np.uint8 = field(default_factory=lambda: np.uint8(0))
    step: np.uint32 = field(default_factory=lambda: np.uint32(0))
    data: bytes = b""

    def to_dict(self) -> dict:
        return {
            "header": self.header.to_dict(),
            "height": int(self.height),
            "width": int(self.width),
            "encoding": self.encoding,
            "is_bigendian": int(self.is_bigendian),
            "step": int(self.step),
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Image":
        return cls(
            header=Header.from_dict(d.get("header", {})),
            height=np.uint32(d.get("height", 0)),
            width=np.uint32(d.get("width", 0)),
            encoding=d.get("encoding", "rgb8"),
            is_bigendian=np.uint8(d.get("is_bigendian", 0)),
            step=np.uint32(d.get("step", 0)),
            data=d.get("data", b""),
        )

    def to_numpy(self) -> np.ndarray:
        """Decode image bytes to numpy array."""
        h, w = int(self.height), int(self.width)
        if self.encoding == "rgb8":
            return np.frombuffer(self.data, dtype=np.uint8).reshape(h, w, 3)
        elif self.encoding == "bgr8":
            return np.frombuffer(self.data, dtype=np.uint8).reshape(h, w, 3)
        elif self.encoding == "mono8":
            return np.frombuffer(self.data, dtype=np.uint8).reshape(h, w)
        elif self.encoding == "nv12":
            # NV12: Y plane + UV interleaved
            y_size = h * w
            uv_size = h * w // 2
            y = np.frombuffer(self.data[:y_size], dtype=np.uint8).reshape(h, w)
            uv = np.frombuffer(self.data[y_size:y_size + uv_size], dtype=np.uint8).reshape(h // 2, w // 2, 2)
            return y, uv
        else:
            raise ValueError(f"Unsupported encoding: {self.encoding}")


@dataclass
class PointField:
    """ROS2 sensor_msgs/PointField equivalent."""
    INT8 = 1
    UINT8 = 2
    INT16 = 3
    UINT16 = 4
    INT32 = 5
    UINT32 = 6
    FLOAT32 = 7
    FLOAT64 = 8

    name: str = ""
    offset: np.uint32 = field(default_factory=lambda: np.uint32(0))
    datatype: np.uint8 = field(default_factory=lambda: np.uint8(7))
    count: np.uint32 = field(default_factory=lambda: np.uint32(1))

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "offset": int(self.offset),
            "datatype": int(self.datatype),
            "count": int(self.count),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PointField":
        return cls(
            name=d.get("name", ""),
            offset=np.uint32(d.get("offset", 0)),
            datatype=np.uint8(d.get("datatype", 7)),
            count=np.uint32(d.get("count", 1)),
        )


@dataclass
class PointCloud2:
    """ROS2 sensor_msgs/PointCloud2 equivalent.

    For zero-copy, point data is stored as raw bytes.
    Use np.frombuffer(msg.data, dtype=np.float32).reshape(-1, fields_count) to decode.
    """
    header: Header = field(default_factory=Header)
    height: np.uint32 = field(default_factory=lambda: np.uint32(1))
    width: np.uint32 = field(default_factory=lambda: np.uint32(0))
    fields: List[PointField] = field(default_factory=list)
    is_bigendian: bool = False
    point_step: np.uint32 = field(default_factory=lambda: np.uint32(16))
    row_step: np.uint32 = field(default_factory=lambda: np.uint32(0))
    data: bytes = b""
    is_dense: bool = False

    def to_dict(self) -> dict:
        return {
            "header": self.header.to_dict(),
            "height": int(self.height),
            "width": int(self.width),
            "fields": [f.to_dict() for f in self.fields],
            "is_bigendian": bool(self.is_bigendian),
            "point_step": int(self.point_step),
            "row_step": int(self.row_step),
            "data": self.data,
            "is_dense": bool(self.is_dense),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PointCloud2":
        return cls(
            header=Header.from_dict(d.get("header", {})),
            height=np.uint32(d.get("height", 1)),
            width=np.uint32(d.get("width", 0)),
            fields=[PointField.from_dict(f) for f in d.get("fields", [])],
            is_bigendian=d.get("is_bigendian", False),
            point_step=np.uint32(d.get("point_step", 16)),
            row_step=np.uint32(d.get("row_step", 0)),
            data=d.get("data", b""),
            is_dense=d.get("is_dense", False),
        )

    def to_numpy(self, field_names: Optional[List[str]] = None) -> np.ndarray:
        """Decode point cloud bytes to numpy array.

        Args:
            field_names: Subset of fields to extract. If None, extracts all fields.
        """
        if not self.fields:
            # Default xyzi layout
            return np.frombuffer(self.data, dtype=np.float32).reshape(-1, 4)

        if field_names is None:
            field_names = [f.name for f in self.fields]

        dtype_list = []
        np_dtype_map = {
            PointField.INT8: np.int8,
            PointField.UINT8: np.uint8,
            PointField.INT16: np.int16,
            PointField.UINT16: np.uint16,
            PointField.INT32: np.int32,
            PointField.UINT32: np.uint32,
            PointField.FLOAT32: np.float32,
            PointField.FLOAT64: np.float64,
        }

        for f in self.fields:
            if f.name in field_names:
                dtype_list.append((f.name, np_dtype_map.get(int(f.datatype), np.float32)))

        return np.frombuffer(self.data, dtype=dtype_list).copy()

    @classmethod
    def from_xyz_array(cls, points: np.ndarray, header: Optional[Header] = None) -> "PointCloud2":
        """Create PointCloud2 from Nx3 or Nx4 numpy array."""
        h = Header(frame_id="lidar") if header is None else header
        n_points = len(points)
        fields = [
            PointField(name="x", offset=np.uint32(0), datatype=np.uint8(7), count=np.uint32(1)),
            PointField(name="y", offset=np.uint32(4), datatype=np.uint8(7), count=np.uint32(1)),
            PointField(name="z", offset=np.uint32(8), datatype=np.uint8(7), count=np.uint32(1)),
        ]
        point_step = 12
        if points.shape[1] >= 4:
            fields.append(PointField(name="intensity", offset=np.uint32(12), datatype=np.uint8(7), count=np.uint32(1)))
            point_step = 16

        return cls(
            header=h,
            height=np.uint32(1),
            width=np.uint32(n_points),
            fields=fields,
            is_bigendian=False,
            point_step=np.uint32(point_step),
            row_step=np.uint32(n_points * point_step),
            data=points.astype(np.float32).tobytes(),
            is_dense=True,
        )


@dataclass
class Imu:
    """ROS2 sensor_msgs/Imu equivalent."""
    header: Header = field(default_factory=Header)
    orientation: Quaternion = field(default_factory=Quaternion)
    orientation_covariance: List[np.float64] = field(default_factory=lambda: [np.float64(0.0)] * 9)
    angular_velocity: "Vector3" = field(default_factory=lambda: __import__("drp_msgs.geometry_msgs", fromlist=["Vector3"]).Vector3())
    angular_velocity_covariance: List[np.float64] = field(default_factory=lambda: [np.float64(0.0)] * 9)
    linear_acceleration: "Vector3" = field(default_factory=lambda: __import__("drp_msgs.geometry_msgs", fromlist=["Vector3"]).Vector3())
    linear_acceleration_covariance: List[np.float64] = field(default_factory=lambda: [np.float64(0.0)] * 9)

    def __post_init__(self):
        from .geometry_msgs import Vector3
        if isinstance(self.angular_velocity, dict):
            self.angular_velocity = Vector3.from_dict(self.angular_velocity)
        if isinstance(self.linear_acceleration, dict):
            self.linear_acceleration = Vector3.from_dict(self.linear_acceleration)

    def to_dict(self) -> dict:
        return {
            "header": self.header.to_dict(),
            "orientation": self.orientation.to_dict(),
            "orientation_covariance": [float(c) for c in self.orientation_covariance],
            "angular_velocity": self.angular_velocity.to_dict(),
            "angular_velocity_covariance": [float(c) for c in self.angular_velocity_covariance],
            "linear_acceleration": self.linear_acceleration.to_dict(),
            "linear_acceleration_covariance": [float(c) for c in self.linear_acceleration_covariance],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Imu":
        from .geometry_msgs import Vector3
        return cls(
            header=Header.from_dict(d.get("header", {})),
            orientation=Quaternion.from_dict(d.get("orientation", {})),
            orientation_covariance=[np.float64(c) for c in d.get("orientation_covariance", [0.0] * 9)],
            angular_velocity=Vector3.from_dict(d.get("angular_velocity", {})),
            angular_velocity_covariance=[np.float64(c) for c in d.get("angular_velocity_covariance", [0.0] * 9)],
            linear_acceleration=Vector3.from_dict(d.get("linear_acceleration", {})),
            linear_acceleration_covariance=[np.float64(c) for c in d.get("linear_acceleration_covariance", [0.0] * 9)],
        )


@dataclass
class NavSatStatus:
    """ROS2 sensor_msgs/NavSatStatus equivalent."""
    STATUS_NO_FIX = -1
    STATUS_FIX = 0
    STATUS_SBAS_FIX = 1
    STATUS_GBAS_FIX = 2

    SERVICE_GPS = 1
    SERVICE_GLONASS = 2
    SERVICE_COMPASS = 4
    SERVICE_GALILEO = 8

    status: np.int8 = field(default_factory=lambda: np.int8(0))
    service: np.uint16 = field(default_factory=lambda: np.uint16(0))

    def to_dict(self) -> dict:
        return {"status": int(self.status), "service": int(self.service)}

    @classmethod
    def from_dict(cls, d: dict) -> "NavSatStatus":
        return cls(
            status=np.int8(d.get("status", 0)),
            service=np.uint16(d.get("service", 0))
        )


@dataclass
class NavSatFix:
    """ROS2 sensor_msgs/NavSatFix equivalent."""
    header: Header = field(default_factory=Header)
    status: NavSatStatus = field(default_factory=NavSatStatus)
    latitude: np.float64 = field(default_factory=lambda: np.float64(0.0))
    longitude: np.float64 = field(default_factory=lambda: np.float64(0.0))
    altitude: np.float64 = field(default_factory=lambda: np.float64(0.0))
    position_covariance: List[np.float64] = field(default_factory=lambda: [np.float64(0.0)] * 9)
    position_covariance_type: np.uint8 = field(default_factory=lambda: np.uint8(0))

    def to_dict(self) -> dict:
        return {
            "header": self.header.to_dict(),
            "status": self.status.to_dict(),
            "latitude": float(self.latitude),
            "longitude": float(self.longitude),
            "altitude": float(self.altitude),
            "position_covariance": [float(c) for c in self.position_covariance],
            "position_covariance_type": int(self.position_covariance_type),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "NavSatFix":
        return cls(
            header=Header.from_dict(d.get("header", {})),
            status=NavSatStatus.from_dict(d.get("status", {})),
            latitude=np.float64(d.get("latitude", 0.0)),
            longitude=np.float64(d.get("longitude", 0.0)),
            altitude=np.float64(d.get("altitude", 0.0)),
            position_covariance=[np.float64(c) for c in d.get("position_covariance", [0.0] * 9)],
            position_covariance_type=np.uint8(d.get("position_covariance_type", 0)),
        )
