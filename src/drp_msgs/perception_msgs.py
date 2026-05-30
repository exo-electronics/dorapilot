"""
perception_msgs — Perception message types

Dorapilot-specific messages inspired by Autoware's tier4_perception_msgs
and VisionPilot's PerceptionContext.
"""

from dataclasses import dataclass, field
from typing import List, Optional
import numpy as np
from .std_msgs import Header
from .geometry_msgs import Point, Quaternion


@dataclass
class LeadVehicle:
    """Lead vehicle detection result.

    Fields:
        distance_m: Longitudinal distance to lead vehicle [m]
        velocity_mps: Lead vehicle velocity [m/s]
        confidence: Detection confidence [0.0, 1.0]
    """
    distance_m: np.float32 = field(default_factory=lambda: np.float32(0.0))
    velocity_mps: np.float32 = field(default_factory=lambda: np.float32(0.0))
    confidence: np.float32 = field(default_factory=lambda: np.float32(0.0))

    def to_dict(self) -> dict:
        return {
            "distance_m": float(self.distance_m),
            "velocity_mps": float(self.velocity_mps),
            "confidence": float(self.confidence),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "LeadVehicle":
        return cls(
            distance_m=np.float32(d.get("distance_m", 0.0)),
            velocity_mps=np.float32(d.get("velocity_mps", 0.0)),
            confidence=np.float32(d.get("confidence", 0.0)),
        )


@dataclass
class LaneLine:
    """Detected lane line.

    Fields:
        points: List of [x, y, z] points in vehicle frame
        confidence: Detection confidence [0.0, 1.0]
        line_type: "left", "right", "center", "ego_edge"
    """
    points: List[List[np.float32]] = field(default_factory=list)
    confidence: np.float32 = field(default_factory=lambda: np.float32(0.0))
    line_type: str = "unknown"

    def to_dict(self) -> dict:
        return {
            "points": [[float(coord) for coord in pt] for pt in self.points],
            "confidence": float(self.confidence),
            "line_type": self.line_type,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "LaneLine":
        return cls(
            points=[[np.float32(c) for c in pt] for pt in d.get("points", [])],
            confidence=np.float32(d.get("confidence", 0.0)),
            line_type=d.get("line_type", "unknown"),
        )


@dataclass
class LaneLineArray:
    """Array of detected lane lines."""
    header: Header = field(default_factory=Header)
    lines: List[LaneLine] = field(default_factory=list)

    def __post_init__(self):
        self.lines = [LaneLine.from_dict(l) if isinstance(l, dict) else l for l in self.lines]

    def to_dict(self) -> dict:
        return {
            "header": self.header.to_dict(),
            "lines": [l.to_dict() for l in self.lines],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "LaneLineArray":
        return cls(
            header=Header.from_dict(d.get("header", {})),
            lines=[LaneLine.from_dict(l) for l in d.get("lines", [])],
        )


@dataclass
class DetectedObject:
    """3D detected object (from LiDAR or camera).

    Fields:
        id: Object tracking ID
        label: Object class ("car", "pedestrian", "cyclist", etc.)
        position: 3D position in vehicle frame [m]
        orientation: Quaternion orientation
        size: [length_m, width_m, height_m]
        velocity_mps: 3D velocity [m/s]
        confidence: Detection confidence [0.0, 1.0]
    """
    id: np.int32 = field(default_factory=lambda: np.int32(-1))
    label: str = "unknown"
    position: Point = field(default_factory=Point)
    orientation: Quaternion = field(default_factory=Quaternion)
    size: List[np.float32] = field(default_factory=lambda: [np.float32(0.0)] * 3)
    velocity_mps: Point = field(default_factory=Point)
    confidence: np.float32 = field(default_factory=lambda: np.float32(0.0))

    def __post_init__(self):
        if isinstance(self.position, dict):
            self.position = Point.from_dict(self.position)
        if isinstance(self.orientation, dict):
            self.orientation = Quaternion.from_dict(self.orientation)
        if isinstance(self.velocity_mps, dict):
            self.velocity_mps = Point.from_dict(self.velocity_mps)

    def to_dict(self) -> dict:
        return {
            "id": int(self.id),
            "label": self.label,
            "position": self.position.to_dict(),
            "orientation": self.orientation.to_dict(),
            "size": [float(s) for s in self.size],
            "velocity_mps": self.velocity_mps.to_dict(),
            "confidence": float(self.confidence),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DetectedObject":
        return cls(
            id=np.int32(d.get("id", -1)),
            label=d.get("label", "unknown"),
            position=Point.from_dict(d.get("position", {})),
            orientation=Quaternion.from_dict(d.get("orientation", {})),
            size=[np.float32(s) for s in d.get("size", [0.0, 0.0, 0.0])],
            velocity_mps=Point.from_dict(d.get("velocity_mps", {})),
            confidence=np.float32(d.get("confidence", 0.0)),
        )


@dataclass
class DetectedObjectArray:
    """Array of 3D detected objects."""
    header: Header = field(default_factory=Header)
    objects: List[DetectedObject] = field(default_factory=list)

    def __post_init__(self):
        self.objects = [DetectedObject.from_dict(o) if isinstance(o, dict) else o for o in self.objects]

    def to_dict(self) -> dict:
        return {
            "header": self.header.to_dict(),
            "objects": [o.to_dict() for o in self.objects],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DetectedObjectArray":
        return cls(
            header=Header.from_dict(d.get("header", {})),
            objects=[DetectedObject.from_dict(o) for o in d.get("objects", [])],
        )


@dataclass
class TrafficLight:
    """Detected traffic light.

    Fields:
        state: "red", "yellow", "green", "unknown"
        position: 3D position in image or vehicle frame
        confidence: Detection confidence [0.0, 1.0]
    """
    state: str = "unknown"
    position: Point = field(default_factory=Point)
    confidence: np.float32 = field(default_factory=lambda: np.float32(0.0))

    def __post_init__(self):
        if isinstance(self.position, dict):
            self.position = Point.from_dict(self.position)

    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "position": self.position.to_dict(),
            "confidence": float(self.confidence),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TrafficLight":
        return cls(
            state=d.get("state", "unknown"),
            position=Point.from_dict(d.get("position", {})),
            confidence=np.float32(d.get("confidence", 0.0)),
        )


@dataclass
class TrafficLightArray:
    """Array of detected traffic lights."""
    header: Header = field(default_factory=Header)
    lights: List[TrafficLight] = field(default_factory=list)

    def __post_init__(self):
        self.lights = [TrafficLight.from_dict(l) if isinstance(l, dict) else l for l in self.lights]

    def to_dict(self) -> dict:
        return {
            "header": self.header.to_dict(),
            "lights": [l.to_dict() for l in self.lights],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TrafficLightArray":
        return cls(
            header=Header.from_dict(d.get("header", {})),
            lights=[TrafficLight.from_dict(l) for l in d.get("lights", [])],
        )


@dataclass
class PerceptionContext:
    """Unified perception output — the single message that drives planning.

    This replaces VisionPilot's scattered ROS2 topics with one structured message.
    Sent by perception_fusion node at 20Hz.

    Fields:
        header: Timestamp + frame_id
        engagement: Driver engagement state (hands on wheel, eyes on road)
        lead: Detected lead vehicle (None if no lead)
        lane_lines: Detected lane boundaries
        objects_3d: Detected 3D objects from LiDAR/camera fusion
        traffic_lights: Detected traffic lights
        safety_events: Active safety events ("stop_line", "pedestrian", etc.)
        speed_limit_mps: Current speed limit from map
        road_condition: "dry", "wet", "snow", "construction"
    """
    header: Header = field(default_factory=Header)
    engagement: bool = False
    lead: Optional[LeadVehicle] = None
    lane_lines: LaneLineArray = field(default_factory=LaneLineArray)
    objects_3d: DetectedObjectArray = field(default_factory=DetectedObjectArray)
    traffic_lights: TrafficLightArray = field(default_factory=TrafficLightArray)
    safety_events: List[str] = field(default_factory=list)
    speed_limit_mps: np.float32 = field(default_factory=lambda: np.float32(0.0))
    road_condition: str = "unknown"

    def __post_init__(self):
        if isinstance(self.lead, dict):
            self.lead = LeadVehicle.from_dict(self.lead)
        if isinstance(self.lane_lines, dict):
            self.lane_lines = LaneLineArray.from_dict(self.lane_lines)
        if isinstance(self.objects_3d, dict):
            self.objects_3d = DetectedObjectArray.from_dict(self.objects_3d)
        if isinstance(self.traffic_lights, dict):
            self.traffic_lights = TrafficLightArray.from_dict(self.traffic_lights)

    def to_dict(self) -> dict:
        return {
            "header": self.header.to_dict(),
            "engagement": bool(self.engagement),
            "lead": self.lead.to_dict() if self.lead else None,
            "lane_lines": self.lane_lines.to_dict(),
            "objects_3d": self.objects_3d.to_dict(),
            "traffic_lights": self.traffic_lights.to_dict(),
            "safety_events": list(self.safety_events),
            "speed_limit_mps": float(self.speed_limit_mps),
            "road_condition": self.road_condition,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PerceptionContext":
        lead_data = d.get("lead")
        return cls(
            header=Header.from_dict(d.get("header", {})),
            engagement=d.get("engagement", False),
            lead=LeadVehicle.from_dict(lead_data) if lead_data else None,
            lane_lines=LaneLineArray.from_dict(d.get("lane_lines", {})),
            objects_3d=DetectedObjectArray.from_dict(d.get("objects_3d", {})),
            traffic_lights=TrafficLightArray.from_dict(d.get("traffic_lights", {})),
            safety_events=list(d.get("safety_events", [])),
            speed_limit_mps=np.float32(d.get("speed_limit_mps", 0.0)),
            road_condition=d.get("road_condition", "unknown"),
        )
