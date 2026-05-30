#!/usr/bin/env python3
"""
Perception fusion node — Dorapilot

Fuses camera + LiDAR outputs into unified PerceptionContext.
Based on VisionPilot's perception_fusion + Autoware's fusion patterns.

For Autoware developers:
    Input: PointCloud2 (from lidar), DetectedObjectArray (from camera)
    Output: PerceptionContext (dorapilot-specific, replaces scattered ROS2 topics)
"""

import time
from dora import Node
import pyarrow as pa

from drp_msgs import (
    Header, PerceptionContext, LeadVehicle, LaneLineArray,
    DetectedObjectArray, TrafficLightArray, PointCloud2
)
from drp_msgs.utils import to_arrow, from_arrow


class PerceptionFusionNode:
    def __init__(self):
        self.node = Node()
        self.latest_camera_objects = DetectedObjectArray()
        self.latest_lidar_objects = DetectedObjectArray()
        self.latest_lane_lines = LaneLineArray()
        self.latest_traffic_lights = TrafficLightArray()

    def fuse_objects(self, camera: DetectedObjectArray, lidar: DetectedObjectArray) -> DetectedObjectArray:
        """Simple fusion: LiDAR provides 3D position, camera provides classification."""
        # TODO: Implement proper data association (Hungarian algorithm, IoU matching)
        # For now, prefer LiDAR objects with camera labels
        fused = DetectedObjectArray(
            header=lidar.header if lidar.header.frame_id else camera.header
        )

        # Use LiDAR objects as base, add camera labels if available
        for lidar_obj in lidar.objects:
            best_match = None
            best_dist = float('inf')
            for cam_obj in camera.objects:
                dist = ((lidar_obj.position.x - cam_obj.position.x) ** 2 +
                       (lidar_obj.position.y - cam_obj.position.y) ** 2) ** 0.5
                if dist < best_dist and dist < 2.0:  # 2m association gate
                    best_dist = dist
                    best_match = cam_obj

            if best_match:
                lidar_obj.label = best_match.label
                lidar_obj.confidence = max(lidar_obj.confidence, best_match.confidence)

            fused.objects.append(lidar_obj)

        return fused

    def extract_lead(self, objects: DetectedObjectArray) -> LeadVehicle:
        """Extract lead vehicle from detected objects."""
        lead = None
        min_dist = float('inf')

        for obj in objects.objects:
            if obj.label in ("car", "truck", "bus"):
                # Must be in front of ego vehicle
                if obj.position.x > 0 and abs(obj.position.y) < 2.0:
                    dist = (obj.position.x ** 2 + obj.position.y ** 2) ** 0.5
                    if dist < min_dist:
                        min_dist = dist
                        lead = LeadVehicle(
                            distance_m=dist,
                            velocity_mps=obj.velocity_mps.x,
                            confidence=obj.confidence
                        )

        return lead

    def on_input(self, event):
        input_id = event["id"]

        if input_id == "objects_3d":
            self.latest_lidar_objects = from_arrow(event["value"], DetectedObjectArray)
        elif input_id == "camera_objects":
            self.latest_camera_objects = from_arrow(event["value"], DetectedObjectArray)
        elif input_id == "lane_lines":
            self.latest_lane_lines = from_arrow(event["value"], LaneLineArray)
        elif input_id == "traffic_lights":
            self.latest_traffic_lights = from_arrow(event["value"], TrafficLightArray)

        # Publish fused context at 20Hz (when any input arrives)
        fused_objects = self.fuse_objects(self.latest_camera_objects, self.latest_lidar_objects)
        lead = self.extract_lead(fused_objects)

        context = PerceptionContext(
            header=Header(
                stamp={"sec": int(time.time()), "nanosec": 0},
                frame_id="base_link"
            ),
            engagement=True,  # TODO: from driver monitoring
            lead=lead,
            lane_lines=self.latest_lane_lines,
            objects_3d=fused_objects,
            traffic_lights=self.latest_traffic_lights,
            safety_events=[],  # TODO: from safety_perception
            speed_limit_mps=16.67,  # TODO: from map
            road_condition="dry"
        )

        self.node.send_output("perception_context", to_arrow(context))

    def run(self):
        print("[perception_fusion] Fusion node started")
        for event in self.node:
            if event["type"] == "INPUT":
                self.on_input(event)
            elif event["type"] == "STOP":
                break


if __name__ == "__main__":
    node = PerceptionFusionNode()
    node.run()
