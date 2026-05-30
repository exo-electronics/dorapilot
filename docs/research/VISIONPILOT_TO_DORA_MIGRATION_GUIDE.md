# VisionPilot → DoraPilot Migration Guide

**Date:** 2026-05-30  
**Status:** Active Development Guide  
**Reference Projects:**
- `~/pilot/visionpilot` — Source ROS2 baseline (~150 packages, `evp_msgs`)
- `~/pilot/autoware.universe` — DORA Autoware reference (dora-rs port)

---

## Executive Summary

This guide provides concrete, line-by-line migration patterns from VisionPilot's ROS2 stack to DoraPilot's DORA-native architecture.

**Key principle:** The migration is **not a rewrite**. It is a **repackaging**:
- Algorithm code stays **unchanged**
- ROS2 `Node` class → DORA `Node` class
- `evp_msgs` → `drp_msgs` (same fields, zero compilation)
- `create_subscription()` / `create_publisher()` → `dataflow.yml` declarations
- `launch/*.launch.py` → `dataflow.yml`

**Key constraint:** Python-only. No C++ nodes, no CMake, no `colcon build`.

---

## 1. Migration Pattern: ROS2 Node → DORA Node

### 1.1 ROS2 Python Node (VisionPilot Style)

```python
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from nav_msgs.msg import Path
from evp_msgs.msg import DetectedObjectArray
from cv_bridge import CvBridge

class DrivingModelNode(Node):
    def __init__(self):
        super().__init__('driving_model')
        self.declare_parameter('model_path', '/data/models/driving_vision.rknn')

        self.sub_image = self.create_subscription(
            Image,
            '/sensing/mono_narrow_preprocessor/image_processed',
            self._on_image, 10
        )
        self.pub_path = self.create_publisher(Path, '/perception/driving_model/path', 10)
        self.pub_leads = self.create_publisher(DetectedObjectArray, '/perception/driving_model/leads', 10)
        self.timer = self.create_timer(1.0/20.0, self._inference_loop)
        self.bridge = CvBridge()
        self.latest_image = None

    def _on_image(self, msg):
        self.latest_image = self.bridge.imgmsg_to_cv2(msg, 'rgb8')

    def _inference_loop(self):
        if self.latest_image is None:
            return
        # ... NPU inference ...
        path_msg = Path()
        self.pub_path.publish(path_msg)
```

### 1.2 DORA Python Node (Dorapilot Style)

```python
from dora import Node
from drp_msgs import Image, Path, DetectedObjectArray
from drp_msgs.utils import to_arrow, from_arrow

class DrivingVisionNode:
    def __init__(self):
        self.node = Node()
        self.model = self._load_model()

    def _load_model(self):
        model_path = self.node.env.get("MODEL_PATH", "/data/models/driving_vision.rknn")
        # ... load RKNN ...
        return model

    def run(self):
        for event in self.node:
            if event["type"] == "INPUT":
                self.on_input(event)
            elif event["type"] == "STOP":
                break

    def on_input(self, event):
        # Deserialize drp_msgs Image from Arrow
        image = from_arrow(event["value"], Image)
        frame = image.to_numpy()  # or cv2 for bgr/rgb

        # ... NPU inference (UNCHANGED algorithm) ...
        path, leads = self.model.infer(frame)

        # Serialize drp_msgs to Arrow and send
        self.node.send_output("neural_path", to_arrow(Path(header=image.header, poses=path)))
        self.node.send_output("leads", to_arrow(DetectedObjectArray(header=image.header, objects=leads)))

if __name__ == "__main__":
    DrivingVisionNode().run()
```

### 1.3 DORA Python Operator (Lightweight, In-Process)

Use operators for preprocessing, filtering, PID control — anything lightweight and stateless.

```python
from dora import DoraStatus
from drp_msgs import Image, PointCloud2
from drp_msgs.utils import to_arrow, from_arrow

class Operator:
    def __init__(self):
        self.target_w = 512
        self.target_h = 256

    def on_event(self, dora_event, send_output):
        if dora_event["type"] == "INPUT":
            return self.on_input(dora_event, send_output)
        return DoraStatus.CONTINUE

    def on_input(self, dora_input, send_output):
        image = from_arrow(dora_input["value"], Image)
        frame = image.to_numpy()

        # RGA hardware resize (or OpenCV fallback)
        resized = cv2.resize(frame, (self.target_w, self.target_h))

        result = Image.from_numpy(resized, header=image.header)
        send_output("image_resized", to_arrow(result))
        return DoraStatus.CONTINUE
```

---

## 2. Migration Pattern: ROS2 Launch → DORA Dataflow YAML

### 2.1 VisionPilot Launch File

```python
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(package='driving_model', executable='driving_model_node',
             name='driving_model',
             parameters=[{'model_path': '/data/models/driving_vision.rknn'}],
             remappings=[('image_raw', '/sensing/mono_narrow_preprocessor/image_processed')]),
        Node(package='lane_detector', executable='lane_detector_node',
             name='lane_detector',
             parameters=[{'model_path': '/data/models/lane_detector.rknn'}]),
        Node(package='perception_fusion', executable='perception_fusion_node',
             name='perception_fusion'),
    ])
```

### 2.2 DORA Dataflow YAML

```yaml
nodes:
  - id: image_preprocess
    operators:
      python: src/sensing/operators/image_preprocess.py
    inputs:
      image_raw: camera/image_raw
    outputs:
      - image_resized
      - image_yuv
    env:
      RESIZE_WIDTH: "512"
      RESIZE_HEIGHT: "256"
      USE_RGA: "true"

  - id: driving_vision
    path: src/perception/driving_vision/driving_vision_node.py
    inputs:
      image: image_preprocess/image_yuv
    outputs:
      - features
      - engagement
    env:
      MODEL_PATH: /data/models/driving_vision_rk3688.rknn
      NPU_CORE: "0"
    restart_policy: on_failure
    max_restarts: 3

  - id: lane_detector
    path: src/perception/lane_detector/lane_detector_node.py
    inputs:
      image: image_preprocess/image_resized
    outputs:
      - lane_lines
    env:
      MODEL_PATH: /data/models/lane_detector_rk3688.rknn
      NPU_CORE: "1"

  - id: perception_fusion
    path: src/perception/perception_fusion/perception_fusion_node.py
    inputs:
      neural_path: driving_vision/neural_path
      lane_lines: lane_detector/lane_lines
      lidar_objects: lidar_detector/objects_3d
      safety_events: safety_perception/safety_events
      gnss_fix: gnss/navsatfix
      imu_raw: imu/imu_data
    outputs:
      - perception_context
```

### 2.3 Key Differences

| Aspect | ROS2 Launch | DORA Dataflow |
|--------|-------------|---------------|
| **Definition** | Python code | Declarative YAML |
| **Node type** | All processes | `path` (standalone) or `operators` (in-process) |
| **Connections** | Topic remappings | `input: node_id/output_id` |
| **Parameters** | `parameters=[{}]` | `env:` dictionary |
| **Timing** | Timer nodes | `dora/timer/millis/N` |
| **Restart** | systemd externally | `restart_policy:` inline |
| **Build** | `colcon build` required | No build — direct execution |

---

## 3. Migration Pattern: evp_msgs → drp_msgs

### 3.1 The Core Change

| VisionPilot | Dorapilot |
|-------------|-----------|
| `evp_msgs/msg/*.msg` files | `src/drp_msgs/*.py` Python dataclasses |
| `rosidl_generate_interfaces` build | Zero compilation — import and use |
| `from evp_msgs.msg import X` | `from drp_msgs import X` |
| CDR serialization | PyArrow zero-copy |

### 3.2 Message Mapping

| VisionPilot (`evp_msgs`) | Dorapilot (`drp_msgs`) |
|--------------------------|------------------------|
| `evp_msgs.msg.EgoState` | `drp_msgs.perception_msgs.PerceptionContext` |
| `evp_msgs.msg.DetectedObjectArray` | `drp_msgs.perception_msgs.DetectedObjectArray` |
| `evp_msgs.msg.DetectedObject` | `drp_msgs.perception_msgs.DetectedObject` |
| `evp_msgs.msg.NeuralPath` | `drp_msgs.planning_msgs.Trajectory` |
| `evp_msgs.msg.NeuralPathPoint` | `drp_msgs.planning_msgs.TrajectoryPoint` |
| `evp_msgs.msg.ControlCommand` | `drp_msgs.vehicle_msgs.VehicleCommand` |
| `std_msgs.msg.Header` | `drp_msgs.std_msgs.Header` |
| `geometry_msgs.msg.Point` | `drp_msgs.geometry_msgs.Point` |
| `geometry_msgs.msg.Quaternion` | `drp_msgs.geometry_msgs.Quaternion` |
| `geometry_msgs.msg.Pose` | `drp_msgs.geometry_msgs.Pose` |
| `sensor_msgs.msg.Image` | `drp_msgs.sensor_msgs.Image` |
| `sensor_msgs.msg.PointCloud2` | `drp_msgs.sensor_msgs.PointCloud2` |
| `sensor_msgs.msg.Imu` | `drp_msgs.sensor_msgs.Imu` |
| `sensor_msgs.msg.NavSatFix` | `drp_msgs.sensor_msgs.NavSatFix` |
| `nav_msgs.msg.Path` | `drp_msgs.nav_msgs.Path` |
| `nav_msgs.msg.Odometry` | `drp_msgs.nav_msgs.Odometry` |

### 3.3 Image Message

**ROS2 (VisionPilot):**
```python
from sensor_msgs.msg import Image
from cv_bridge import CvBridge

bridge = CvBridge()
msg = Image(height=256, width=512, encoding='rgb8', data=frame.tobytes())
frame = bridge.imgmsg_to_cv2(msg, 'rgb8')
```

**DORA (Dorapilot with drp_msgs):**
```python
from drp_msgs import Image
from drp_msgs.utils import to_arrow, from_arrow

# Publish
image = Image.from_numpy(frame, header=Header(frame_id="camera"))
send_output("image", to_arrow(image))

# Subscribe
image = from_arrow(event["value"], Image)
frame = image.to_numpy()  # zero-copy numpy view
```

### 3.4 PointCloud2 Message

**ROS2 (VisionPilot):**
```python
from sensor_msgs.msg import PointCloud2, PointField

msg = PointCloud2()
msg.height = 1
msg.width = len(points)
msg.fields = [
    PointField(name='x', offset=0, datatype=PointField.FLOAT32, count=1),
    PointField(name='y', offset=4, datatype=PointField.FLOAT32, count=1),
    PointField(name='z', offset=8, datatype=PointField.FLOAT32, count=1),
]
msg.point_step = 16
msg.row_step = msg.point_step * len(points)
msg.data = points.tobytes()
```

**DORA (Dorapilot with drp_msgs):**
```python
from drp_msgs import PointCloud2, Header
from drp_msgs.utils import to_arrow, from_arrow

# Publish (from numpy array Nx4)
pc2 = PointCloud2.from_xyz_array(points, header=Header(frame_id="lidar"))
send_output("pointcloud", to_arrow(pc2))

# Subscribe
pc2 = from_arrow(event["value"], PointCloud2)
points = pc2.to_numpy()  # Nx4 float32 array [x, y, z, intensity]
```

**⚠️ Critical:** DORA's ROS2 bridge has known issues with PointCloud2 struct arrays. For dorapilot:
- **Keep LiDAR pipeline 100% DORA-native** — do NOT bridge PointCloud2 to ROS2
- Use `drp_msgs.PointCloud2` end-to-end within DORA
- Bridge only at the vehicle boundary with simple structs

### 3.5 Pose/Path Messages (ROS2 Bridge)

For nodes that MUST publish to ROS2 (vehicle bridge only):

```python
from drp_msgs import PoseStamped, Path
from drp_msgs.utils import to_arrow, from_arrow
import dora

# Inside bridge node: convert drp_msgs → ROS2-compatible dict
path = Path(header=Header(frame_id="map"), poses=[...])
ros2_dict = path.to_dict()  # ROS2-compatible structure

# Publish via DORA ROS2 bridge
publisher.publish(pa.array([ros2_dict]))
```

---

## 4. Migration Pattern: ROS2 Services → DORA Nodes

### 4.1 VisionPilot Inference Service

```python
from rclpy.node import Node
from evp_msgs.srv import LoadModel, RunInference

class InferenceNode(Node):
    def __init__(self):
        super().__init__('inference')
        self.srv_load = self.create_service(LoadModel, '/system/inference/load_model', self._handle_load)
        self.srv_infer = self.create_service(RunInference, '/system/inference/infer', self._handle_infer)

    def _handle_infer(self, request, response):
        backend = self.backends[request.backend]
        outputs = backend.infer(request.model_id, request.input_data)
        response.outputs = outputs
        return response
```

### 4.2 DORA Inference Daemon

In DORA, request/response becomes dataflow connections:

```yaml
nodes:
  - id: inference_daemon
    path: src/system/inference_daemon/inference_daemon.py
    inputs:
      infer_request: perception/driving_vision/infer_request
    outputs:
      - infer_result
    env:
      NPU_CORE_0_MODELS: "driving_vision,driving_policy"
      NPU_CORE_1_MODELS: "lane_detector,lidar_perception"
```

**Client pattern (inside perception node):**
```python
# Instead of: client.call_async(request)
# Send inference request as output
send_output("infer_request", to_arrow(infer_request))

# Receive result as input
if event["id"] == "infer_result":
    result = from_arrow(event["value"], InferResult)
```

**Key difference:** ROS2 services are synchronous request/response. DORA is **always asynchronous dataflow**.

---

## 5. Module-by-Module Migration Map

### 5.1 Sensing Layer

| VisionPilot (ROS2) | Dorapilot (DORA) | Notes |
|-------------------|------------------|-------|
| `camera_driver` | `camera/camera_node.py` | V4L2 capture, outputs `drp_msgs.Image` |
| `hesai_driver` | `lidar/lidar_node.py` | Pandar QT64, outputs `drp_msgs.PointCloud2` |
| `image_preprocessor` | `operators/image_preprocess.py` | In-process operator, zero overhead |
| `stereo_matcher` | `stereo/stereo_node.py` | Python OpenCV SGM |
| `sensing_quality` | `operators/quality_operator.py` | Lightweight operator |

### 5.2 Perception Layer

| VisionPilot (ROS2) | Dorapilot (DORA) | Notes |
|-------------------|------------------|-------|
| `driving_model` | `driving_vision/driving_vision_node.py` | NPU Core 0, isolated process |
| `lane_detector` | `lane_detector/lane_detector_node.py` | NPU Core 1 |
| `lidar_detector` | `lidar_detector/lidar_detector_node.py` | PointPillars on NPU |
| `perception_fusion` | `perception_fusion/perception_fusion_node.py` | Outputs `PerceptionContext` |
| `object_tracker` | `tracker_operator.py` | Kalman filter operator |
| `crop_box_filter` | `operators/pointcloud_filter.py` | Voxel + crop box operator |
| `voxel_grid_filter` | merged into `pointcloud_filter.py` | No separate package |

### 5.3 Planning Layer

| VisionPilot (ROS2) | Dorapilot (DORA) | Notes |
|-------------------|------------------|-------|
| `behavior_planner` | `behavior_planner/behavior_planner_node.py` | Consumes `PerceptionContext` |
| `trajectory_planner` | `trajectory_planner/trajectory_planner_node.py` | ACADOS Python interface |
| `velocity_smoother` | `operators/smoother_operator.py` | In-process filter |
| `trajectory_comparator` | `trajectory_selector/trajectory_selector_node.py` | Selects best trajectory |

### 5.4 Control Layer

| VisionPilot (ROS2) | Dorapilot (DORA) | Notes |
|-------------------|------------------|-------|
| `vehicle_controller` | `controller/controller_node.py` | 100Hz PID node |
| `trajectory_follower` | `operators/follower_operator.py` | In-process path tracking |
| `lat_control_torque` | `operators/lateral_pid_operator.py` | In-process PID |
| `long_control` | `operators/longitudinal_pid_operator.py` | In-process PID |

### 5.5 Localization Layer

| VisionPilot (ROS2) | Dorapilot (DORA) | Notes |
|-------------------|------------------|-------|
| `ekf_localizer` | `ekf_localizer/ekf_localizer_node.py` | Python filterpy/numpy EKF |
| `ndt_localizer` | `ndt_localizer/ndt_localizer_node.py` | Python NDT (open3d/pyntcloud) |
| `gnss_localizer` | `gnss_poser/gnss_poser_node.py` | GNSS → pose |

---

## 6. Concrete Example: Perception Fusion Node Migration

This example shows migrating VisionPilot's perception fusion to DORA using **drp_msgs**.

### 6.1 Original ROS2 Node (Conceptual)

```python
import rclpy
from rclpy.node import Node
from evp_msgs.msg import EgoState, DetectedObjectArray, NeuralPath
from sensor_msgs.msg import Image

class PerceptionFusionNode(Node):
    def __init__(self):
        super().__init__('perception_fusion')
        self.sub_objects = self.create_subscription(DetectedObjectArray, '/perception/objects', self.on_objects, 10)
        self.sub_path = self.create_subscription(NeuralPath, '/perception/neural_path', self.on_path, 10)
        self.pub_ego = self.create_publisher(EgoState, '/perception/ego_state', 10)

    def on_objects(self, msg):
        self.latest_objects = msg

    def on_path(self, msg):
        self.latest_path = msg
        ego = self.fuse(self.latest_objects, self.latest_path)
        self.pub_ego.publish(ego)
```

### 6.2 Migrated DORA Node

**File:** `src/perception/perception_fusion/perception_fusion_node.py`

```python
from dora import Node
from drp_msgs import (
    PerceptionContext, DetectedObjectArray, Trajectory,
    LeadVehicle, LaneLineArray, Header
)
from drp_msgs.utils import to_arrow, from_arrow

class PerceptionFusionNode:
    def __init__(self):
        self.node = Node()
        self.latest_objects = DetectedObjectArray()
        self.latest_path = Trajectory()
        self.latest_lane_lines = LaneLineArray()

    def run(self):
        for event in self.node:
            if event["type"] == "INPUT":
                self.on_input(event)
            elif event["type"] == "STOP":
                break

    def on_input(self, event):
        if event["id"] == "objects_3d":
            self.latest_objects = from_arrow(event["value"], DetectedObjectArray)
        elif event["id"] == "neural_path":
            self.latest_path = from_arrow(event["value"], Trajectory)
        elif event["id"] == "lane_lines":
            self.latest_lane_lines = from_arrow(event["value"], LaneLineArray)

        # Fuse when all inputs available
        if self.latest_objects.objects and self.latest_path.points:
            ctx = self.fuse()
            self.node.send_output("perception_context", to_arrow(ctx))

    def fuse(self) -> PerceptionContext:
        """Fusion logic — UNCHANGED from VisionPilot."""
        lead = self._extract_lead(self.latest_objects)
        return PerceptionContext(
            header=Header(frame_id="base_link"),
            lead=lead,
            lane_lines=self.latest_lane_lines,
            objects_3d=self.latest_objects,
            speed_limit_mps=16.67,
            road_condition="dry"
        )

    def _extract_lead(self, objects: DetectedObjectArray) -> LeadVehicle:
        # ... same logic as VisionPilot ...
        pass

if __name__ == "__main__":
    PerceptionFusionNode().run()
```

### 6.3 Migration Takeaway

> **Algorithm code is untouched.** The only changes are:
> 1. Replace `rclpy.Node` with `dora.Node`
> 2. Replace `evp_msgs.msg.X` with `drp_msgs.X`
> 3. Replace `create_subscription()` with `for event in self.node:`
> 4. Replace `publish()` with `self.node.send_output()`
> 5. Replace CDR serialization with `to_arrow()` / `from_arrow()`

This is a **wrapper migration**, not a rewrite.

---

## 7. Migration Pattern: ROS2 Parameters → DORA Environment

### 7.1 VisionPilot Parameters

```python
# ROS2 parameter declaration
self.declare_parameters(namespace='', parameters=[
    ('model_path', '/data/models/driving_vision.rknn'),
    ('inference_rate_hz', 20.0),
    ('npu_core_id', 0),
])

# Usage
model_path = self.get_parameter('model_path').value
```

### 7.2 DORA Parameters

```yaml
nodes:
  - id: driving_vision
    path: src/perception/driving_vision/driving_vision_node.py
    inputs:
      image: image_preprocess/image_yuv
    outputs:
      - features
    env:
      MODEL_PATH: /data/models/driving_vision_rk3688.rknn
      INFERENCE_RATE_HZ: "20"
      NPU_CORE_ID: "0"
```

```python
# In node code
model_path = self.node.env.get("MODEL_PATH", "/data/models/default.rknn")
npu_core = int(self.node.env.get("NPU_CORE_ID", "0"))
```

---

## 8. Build System Migration

### 8.1 VisionPilot Build

```bash
cd ~/visionpilot_ws
colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release
source install/setup.bash
```

### 8.2 Dorapilot Build

```bash
# Install DORA CLI and Python API (one-time)
pip install dora-rs numpy pyarrow

# Run dataflow — no build step
cd ~/pilot/dorapilot
dora run dataflows/dorapilot_main.yml
```

**No colcon, no CMake, no package.xml, no setup.py, no C++ compilation.** Pure Python + YAML.

---

## 9. Testing Migration: rosbag → dora record/replay

### 9.1 VisionPilot Testing

```bash
# Record
ros2 bag record /sensing/camera/image_raw /sensing/lidar/points

# Replay (cannot substitute nodes)
ros2 bag play bag_file/
```

### 9.2 Dorapilot Testing

```bash
# Record
dora record dataflows/dorapilot_main.yml --output test_drive.drec

# Replay with experimental model
dora replay test_drive.drec \
  --substitute driving_vision:experimental_model.py \
  --speed 2.0

# Replay for regression testing
dora replay test_drive.drec --assert
```

---

## 10. Checklist: Migrating a Single VisionPilot Node

- [ ] **Copy algorithm code**: Reuse Python implementation unchanged
- [ ] **Replace ROS2 imports**: Remove `rclpy`, `sensor_msgs`, `evp_msgs`
- [ ] **Add DORA imports**: `from dora import Node` or `from dora import DoraStatus`
- [ ] **Add drp_msgs imports**: `from drp_msgs import X` (map from `evp_msgs.msg`)
- [ ] **Replace init**: `rclpy.init()` → `Node()`
- [ ] **Replace subscribers**: `create_subscription()` → `for event in node:`
- [ ] **Replace publishers**: `create_publisher()` + `publish()` → `send_output()`
- [ ] **Replace timers**: `create_timer()` → `dora/timer/millis/N` in YAML
- [ ] **Replace parameters**: `declare_parameter()` → `self.node.env.get()`
- [ ] **Serialize data**: `evp_msgs` → `to_arrow()` / `from_arrow()`
- [ ] **Add to dataflow.yml**: Declare node ID, inputs, outputs, env
- [ ] **Test standalone**: `dora run dataflows/test.yml`
- [ ] **Validate timing**: `dora topic hz <node>/<output>`

---

## References

| Project | Path | What to Learn |
|---------|------|---------------|
| **dora-autoware.universe** | `~/pilot/autoware.universe` | DORA port patterns — NDT, EKF, GNSS, YOLO |
| **YOLO operator** | `src/perception/yolo/object_detection_yolov5.py` | ML inference operator |
| **Camera node** | `src/sensing/camera/camera_node.py` | Image capture → drp_msgs.Image |
| **LiDAR node** | `src/sensing/lidar/lidar_node.py` | Pandar QT64 → drp_msgs.PointCloud2 |
| **Perception fusion** | `src/perception/perception_fusion/perception_fusion_node.py` | Multi-input fusion with drp_msgs |
| **Dataflow** | `dataflows/dorapilot_main.yml` | Full pipeline YAML |

---

*Migration guide v2.0 — 2026-05-30 — drp_msgs Edition*
