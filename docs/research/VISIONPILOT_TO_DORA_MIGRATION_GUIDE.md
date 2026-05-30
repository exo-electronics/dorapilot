# VisionPilot → DoraPilot Migration Guide

**Date:** 2026-05-30  
**Status:** Reference Implementation Guide  
**Reference Projects:**
- `~/pilot/visionpilot` — Source ROS2 baseline
- `~/pilot/autoware.universe` — DORA Autoware reference (dora-rs port)

---

## Executive Summary

This document provides concrete, line-by-line migration patterns for transforming VisionPilot's ROS2 Humble stack into DoraPilot's DORA-native architecture. Every pattern is validated against the **dora-autoware.universe** project, which has already successfully ported Autoware modules (NDT localization, EKF, IMU corrector, GNSS poser, YOLO perception) to DORA with real-vehicle deployment.

**Key constraint:** DoraPilot is **Python-only**. All nodes, operators, and algorithms are implemented in Python. No C++ nodes, no CMake, no Rust required for application code. DORA's Python API is first-class and production-ready.

**Key insight from dora-autoware.universe:** The migration is **not a rewrite**. It is a **repackaging**:
- ROS2 `Node` class → DORA `Operator` class or Python `Node` class
- `create_subscription()` / `create_publisher()` → `dataflow.yml` input/output declarations
- `sensor_msgs/Image` → `pyarrow.Array` (numpy buffer view)
- `launch/*.launch.py` → `dataflow.yml`
- Service-based HAL (`/system/inference/infer`) → DORA node with direct outputs

---

## 1. Migration Pattern: ROS2 Node → DORA Operator/Node

### 1.1 ROS2 Python Node (VisionPilot Style)

**Source:** `visionpilot/src/perception/driving_model/driving_model/driving_model_node.py`

```python
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from nav_msgs.msg import Path
from cv_bridge import CvBridge

class DrivingModelNode(Node):
    def __init__(self):
        super().__init__('driving_model')
        
        # Parameters
        self.declare_parameter('model_path', '/data/models/driving_vision.rknn')
        self.declare_parameter('inference_rate_hz', 20.0)
        
        # Subscribers
        self.sub_image = self.create_subscription(
            Image,
            '/sensing/mono_narrow_preprocessor/image_processed',
            self._on_image,
            10
        )
        
        # Publishers
        self.pub_path = self.create_publisher(Path, '/perception/driving_model/path', 10)
        self.pub_leads = self.create_publisher(DetectedObjectArray, '/perception/driving_model/leads', 10)
        
        # Timer
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
        # ... populate ...
        self.pub_path.publish(path_msg)
```

### 1.2 DORA Python Operator (DoraPilot Style)

**Reference:** `autoware.universe/peception/yolo/object_detection_yolov5.py`

```python
import cv2
import numpy as np
import pyarrow as pa
from dora import DoraStatus

class Operator:
    """DORA operator — runs in-process, lightweight transform."""
    
    def __init__(self):
        # No ROS init needed. DORA runtime handles lifecycle.
        self.model = load_rknn_model('/data/models/driving_vision.rknn', core_id=0)
    
    def on_event(self, dora_event, send_output) -> DoraStatus:
        if dora_event["type"] == "INPUT":
            return self.on_input(dora_event, send_output)
        return DoraStatus.CONTINUE
    
    def on_input(self, dora_input, send_output):
        # Input arrives as PyArrow Array — zero-copy numpy view
        frame = dora_input["value"].to_numpy().reshape((256, 512, 3))
        
        # NPU inference
        outputs = self.model.infer(frame)
        
        # Output as PyArrow arrays
        path_array = pa.array(parse_path(outputs).ravel())
        leads_array = pa.array(parse_leads(outputs).ravel())
        
        send_output("path", path_array, dora_input["metadata"])
        send_output("leads", leads_array, dora_input["metadata"])
        
        return DoraStatus.CONTINUE
```

### 1.3 DORA Python Node (For isolated heavy compute)

**Use case:** NPU inference nodes, MPC solvers, or any node that must crash in isolation.

```python
from dora import Node
import pyarrow as pa
import numpy as np
import json

class NdtLocalizerNode:
    """DORA Python node — standalone process, isolated from others."""
    
    def __init__(self):
        self.node = Node()
        self.ndt = load_ndt_solver()      # Reuse your Python algorithm
        self.map_loader = load_pcd_map()  # Reuse your Python map loader
    
    def run(self):
        for event in self.node:
            if event["type"] == "INPUT":
                self.on_input(event)
            elif event["type"] == "STOP":
                break
    
    def on_input(self, event):
        # Receive raw bytes — same memory layout as ROS2 PointCloud2
        data = event["value"].to_numpy().view(np.uint8)
        
        # Parse pointcloud in Python (numpy vectorized)
        points = parse_pointcloud_bytes(data)  # Your existing Python parser
        
        # Run NDT — reuse existing Python/NumPy algorithm
        result = self.ndt.align(points)
        
        if result.is_converged:
            # Serialize pose to JSON for cross-language compatibility
            pose_json = json.dumps({
                "pose": {
                    "position": {
                        "x": result.pose.position.x,
                        "y": result.pose.position.y,
                        "z": result.pose.position.z,
                    },
                    "orientation": {
                        "x": result.pose.orientation.x,
                        "y": result.pose.orientation.y,
                        "z": result.pose.orientation.z,
                        "w": result.pose.orientation.w,
                    }
                }
            })
            self.node.send_output("resultpose", pa.array([pose_json]))

if __name__ == "__main__":
    node = NdtLocalizerNode()
    node.run()
```

**Dataflow declaration (YAML):**
```yaml
nodes:
  - id: ndt_localizer
    path: src/localization/ndt_localizer_node/ndt_localizer_node.py
    inputs:
      pointcloud: lidar/pointcloud
    outputs:
      - resultpose
    env:
      MAP_PATH: /data/maps/current.pcd
      RESOLUTION: "1.0"
```

**No build step needed.** DORA runs Python files directly.

---

## 2. Migration Pattern: ROS2 Launch → DORA Dataflow YAML

### 2.1 VisionPilot Launch File (ROS2)

**Source:** `visionpilot/src/launch/visionpilot_launch/launch/perception.launch.py`

```python
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package='driving_model',
            executable='driving_model_node',
            name='driving_model',
            parameters=[{'model_path': '/data/models/driving_vision.rknn'}],
            remappings=[
                ('image_raw', '/sensing/mono_narrow_preprocessor/image_processed'),
            ]
        ),
        Node(
            package='lane_detector',
            executable='lane_detector_node',
            name='lane_detector',
            parameters=[{'model_path': '/data/models/lane_detector.rknn'}],
        ),
        Node(
            package='perception_fusion',
            executable='perception_fusion_node',
            name='perception_fusion',
        ),
    ])
```

### 2.2 DORA Dataflow YAML

**Reference:** `autoware.universe/peception/yolo/dataflow_yolo.yaml`

```yaml
# dorapilot/perception/dataflow.yml
nodes:
  # Camera preprocess (operator — lightweight, in-process)
  - id: image_preprocess
    operator:
      python: operators/image_preprocess.py
      inputs:
        image_raw: camera/image_raw
      outputs:
        - image_processed
    env:
      RESIZE_WIDTH: 512
      RESIZE_HEIGHT: 256
      USE_RGA: "true"

  # Driving vision (node — isolated process, NPU heavy)
  - id: driving_vision
    path: src/perception/driving_vision_node/driving_vision_node.py
    inputs:
      image: image_preprocess/image_processed
    outputs:
      - features
      - engagement
    env:
      MODEL_PATH: /data/models/driving_vision_rk3688.rknn
      NPU_CORE: "0"
    restart_policy: on_failure
    max_restarts: 3

  # Lane detection (node — isolated process, NPU heavy)
  - id: lane_detector
    path: src/perception/lane_detector_node/lane_detector_node.py
    inputs:
      image: image_preprocess/image_processed
    outputs:
      - lane_lines
    env:
      MODEL_PATH: /data/models/lane_detector_rk3688.rknn
      NPU_CORE: "1"

  # Perception fusion (node — CPU, combines all inputs)
  - id: perception_fusion
    path: src/perception/perception_fusion_node/perception_fusion_node.py
    inputs:
      features: driving_vision/features
      lane_lines: lane_detector/lane_lines
      lidar_objects: lidar_perception/objects_3d
      safety_events: safety_perception/safety_events
    outputs:
      - perception_context
```

### 2.3 Key Differences

| Aspect | ROS2 Launch | DORA Dataflow |
|--------|-------------|---------------|
| **Definition** | Python code | Declarative YAML |
| **Node type** | All are processes | `operator` (in-process) or `custom` (standalone) |
| **Connections** | Topic remappings | `input: node_id/output_id` |
| **Parameters** | `parameters=[{}]` | `env:` or `params:` |
| **Timing** | External timer nodes | `dora/timer/millis/N` or `dora/timer/hz/N` |
| **Restart** | systemd externally | `restart_policy:` inline |

---

## 3. Migration Pattern: ROS2 Messages → PyArrow Arrays

### 3.1 Image Message

**ROS2:**
```python
from sensor_msgs.msg import Image
from cv_bridge import CvBridge

bridge = CvBridge()
msg = Image()
msg.height = 256
msg.width = 512
msg.encoding = 'rgb8'
msg.data = frame.tobytes()

# Subscribe
frame = bridge.imgmsg_to_cv2(msg, 'rgb8')
```

**DORA (Reference: autoware.universe/dora-hardware/vendors/camera/OpenCV/webcam.py):**
```python
import pyarrow as pa
import numpy as np

# Publish
send_output("image", pa.array(frame.ravel().view(np.uint8)), metadata)

# Subscribe
frame = dora_input["value"].to_numpy().reshape((256, 512, 3))
```

### 3.2 PointCloud2 Message

**ROS2:**
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

**DORA (Reference: autoware.universe/dora-hardware/dora_to_ros2/lidar/lidar_to_ros2.py):**
```python
# DORA passes raw bytes directly — no PointField metadata needed
# The dataflow contract (YAML) defines the schema implicitly

# Publish
send_output("pointcloud", pa.array(points.ravel().view(np.uint8)))

# Subscribe (Python node)
import numpy as np

data = dora_input["value"].to_numpy().view(np.uint8)

# Parse directly — same memory layout as ROS2 PointCloud2
header_seq = int.from_bytes(data[0:4], 'little')
header_stamp = int.from_bytes(data[8:16], 'little')
points = []
for i in range((len(data) - 16) // 16):
    offset = 16 + 16 * i
    x = np.frombuffer(data[offset:offset+4], dtype=np.float32)[0]
    y = np.frombuffer(data[offset+4:offset+8], dtype=np.float32)[0]
    z = np.frombuffer(data[offset+8:offset+12], dtype=np.float32)[0]
    intensity = np.frombuffer(data[offset+12:offset+16], dtype=np.float32)[0]
    points.append([x, y, z, intensity])
points = np.array(points, dtype=np.float32)
```

**⚠️ Critical:** DORA's ROS2 bridge has known issues with PointCloud2 `Struct array` panics. For dorapilot:
- **Keep LiDAR pipeline 100% DORA-native** — do NOT bridge PointCloud2 to ROS2
- Bridge only at the end: `trajectory` → `nav_msgs::Path` → ROS2 vehicle controller

### 3.3 Pose/Path Messages

**DORA → ROS2 Bridge (Reference: autoware.universe/localization/ndt_localizer/src/pose_to_ros2.py):**
```python
import dora
import pyarrow as pa
import numpy as np

class Operator:
    def __init__(self):
        self.ros2_context = dora.experimental.ros2_bridge.Ros2Context()
        self.ros2_node = self.ros2_context.new_node(
            "path2ros", "/ros2_bridge",
            dora.experimental.ros2_bridge.Ros2NodeOptions(rosout=True)
        )
        self.topic_qos = dora.experimental.ros2_bridge.Ros2QosPolicies(
            reliable=True, max_blocking_time=0.1
        )
        self.path_topic = self.ros2_node.create_topic(
            "/ros2_bridge/Path_data", "nav_msgs::Path", self.topic_qos
        )
        self.path_publisher = self.ros2_node.create_publisher(self.path_topic)
    
    def on_input(self, dora_input, send_output):
        data = dora_input["value"].to_pylist()
        json_string = ''.join(chr(int(num)) for num in data)
        pose_dict = json.loads(json_string)
        
        ros_path = {
            'header': {'frame_id': 'map', 'stamp': {'sec': 111, 'nanosec': 222}},
            'poses': [{
                'pose': {
                    'position': {'x': pose_dict['pose']['position']['x'], ...},
                    'orientation': {'w': pose_dict['pose']['orientation']['w'], ...}
                }
            }]
        }
        self.path_publisher.publish(pa.array([ros_path]))
```

---

## 4. Migration Pattern: ROS2 Services → DORA Nodes/Outputs

### 4.1 VisionPilot Inference Service (ROS2)

**Source:** `visionpilot/src/system/inference/inference/inference_node.py`

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

In DORA, service-like request/response is replaced by **dataflow connections**. The inference daemon becomes a node with inputs and outputs:

```yaml
# system/dataflow.yml
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

**Python client pattern (inside perception node):**
```python
# Instead of: client.call_async(request)
# DORA perception node sends inference request as output
send_output("infer_request", pa.array(preprocessed_image.ravel()))

# And receives result as input in next on_input call
if dora_input["id"] == "infer_result":
    result = dora_input["value"].to_numpy()
```

**Key difference:** ROS2 services are synchronous request/response. DORA is **always asynchronous dataflow**. If you need synchronous behavior, buffer the request and match on response ID.

---

## 5. Module-by-Module Migration Map

### 5.1 Sensing Layer

| VisionPilot (ROS2) | DoraPilot (DORA) | Reference | Notes |
|-------------------|------------------|-----------|-------|
| `camera_driver` (ROS2 Node) | `camera_node` (Operator) | `autoware.universe/dora-hardware/vendors/camera/OpenCV/webcam.py` | Use OpenCV capture, output PyArrow array |
| `hesai_driver` (ROS2 Node) | `lidar_node` (Python Node) | `autoware.universe/dora-hardware/vendors/lidar/dataflow.yml` | Raw bytes output, 16-byte header + point data |
| `image_preprocessor` (ROS2 Node) | `image_preprocess` (Operator) | `autoware.universe/peception/yolo/webcam.py` | In-process RGA resize, zero overhead |
| `stereo_matcher` (ROS2 Node) | `stereo_node` (Python Node) | — | Python OpenCV SGM or NumPy-based stereo |
| `sensing_quality` (ROS2 Node) | `quality_operator` (Operator) | — | Lightweight analysis, in-process |

**Dataflow:**
```yaml
nodes:
  - id: camera
    operator:
      python: src/sensing/operators/camera_op.py
      inputs:
        tick: dora/timer/millis/33
      outputs:
        - image_raw

  - id: image_preprocess
    operator:
      python: src/sensing/operators/image_preprocess.py
      inputs:
        image_raw: camera/image_raw
      outputs:
        - image_processed
```

### 5.2 Perception Layer

| VisionPilot (ROS2) | DoraPilot (DORA) | Reference | Notes |
|-------------------|------------------|-----------|-------|
| `driving_model` (ROS2 Node) | `driving_vision_node` (Custom Node) | `autoware.universe/peception/yolo/object_detection_yolov5.py` | NPU inference, isolated process |
| `lane_detector` (ROS2 Node) | `lane_detector_node` (Custom Node) | — | Same pattern as driving_vision |
| `lidar_detector` (ROS2 Node) | `lidar_perception_node` (Custom Node) | — | PointPillars on NPU Core 1 |
| `perception_fusion` (ROS2 Node) | `perception_fusion_node` (Custom Node) | — | Multi-input, CPU-based |
| `object_tracker` (ROS2 Node) | `tracker_operator` (Operator) | — | Kalman filter as lightweight operator |
| `crop_box_filter` (ROS2 Node) | `filter_operators` (Operator) | — | In-process voxel + crop box |
| `voxel_grid_filter` (ROS2 Node) | merged into `filter_operators` | — | No separate package needed |

### 5.3 Planning Layer

| VisionPilot (ROS2) | DoraPilot (DORA) | Reference | Notes |
|-------------------|------------------|-----------|-------|
| `behavior_planner` (ROS2 Node) | `behavior_planner_node` (Python Node) | — | Python logic |
| `trajectory_planner` (ROS2 Node) | `trajectory_planner_node` (Python Node) | — | ACADOS Python interface + generated C solver |
| `velocity_smoother` (ROS2 Node) | `smoother_operator` (Operator) | — | In-process filter |
| `trajectory_comparator` (ROS2 Node) | `trajectory_selector_node` (Python Node) | — | Selects best trajectory |

### 5.4 Control Layer

| VisionPilot (ROS2) | DoraPilot (DORA) | Reference | Notes |
|-------------------|------------------|-----------|-------|
| `vehicle_controller` (ROS2 Node) | `controller_node` (Custom Node) | — | 100Hz control loop |
| `trajectory_follower` (ROS2 Node) | `follower_operator` (Operator) | — | In-process path tracking |
| `lat_control_torque` (ROS2 Node) | `lateral_pid_operator` (Operator) | — | In-process PID |
| `long_control` (ROS2 Node) | `longitudinal_pid_operator` (Operator) | — | In-process PID |

### 5.5 System Layer

| VisionPilot (ROS2) | DoraPilot (DORA) | Reference | Notes |
|-------------------|------------------|-----------|-------|
| `inference_ecu` (ROS2 Service Node) | `inference_daemon` (Custom Node) | — | Exposes NPU/GPU/RGA via outputs |
| `camera_daemon` (ROS2 Node) | `camera_daemon` (Custom Node) | — | V4L2/ISP hardware management |
| `thermal` (ROS2 Node) | `thermal_daemon` (Operator) | — | Lightweight monitoring |
| `health_monitor` (ROS2 Node) | `health_daemon` (Operator) | — | System health telemetry |

### 5.6 Localization Layer

| VisionPilot (ROS2) | DoraPilot (DORA) | Reference | Notes |
|-------------------|------------------|-----------|-------|
| `ekf_localizer` (ROS2 Node) | `ekf_localizer_node` (Python Node) | `autoware.universe/localization/ekf_localizer/dataflow.yml` | Python filterpy or NumPy EKF |
| `ndt_localizer` (ROS2 Node) | `ndt_localizer_node` (Python Node) | — | Python open3d or pyntcloud NDT |
| `gnss_localizer` (ROS2 Node) | `gnss_poser` (Python Node) | `autoware.universe/sensing/gnss_poser/dataflow.yml` | GNSS → pose, Python geodesy |

---

## 6. Concrete Example: Localization Node Migration (Python-Only)

This example shows how to migrate a ROS2 localization node to DORA using **pure Python**.

### 6.1 Original ROS2 Node (Conceptual)

```python
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import PointCloud2
from geometry_msgs.msg import PoseStamped

class LocalizerNode(Node):
    def __init__(self):
        super().__init__('localizer')
        self.sub = self.create_subscription(PointCloud2, '/sensing/lidar/points', self.on_cloud, 10)
        self.pub = self.create_publisher(PoseStamped, '/localization/pose', 10)
        self.map = load_map()  # Your existing Python map loader
    
    def on_cloud(self, msg):
        points = pointcloud2_to_numpy(msg)  # Your existing Python parser
        pose = self.ndt_align(points)         # Your existing Python algorithm
        self.pub.publish(pose)
```

### 6.2 Migrated DORA Python Node

**File:** `src/localization/localizer_node/localizer_node.py`

```python
from dora import Node
import pyarrow as pa
import numpy as np
import json

class LocalizerNode:
    """DORA Python node — standalone process. Algorithm code is untouched."""
    
    def __init__(self):
        self.node = Node()
        self.map = load_map()  # Your existing Python map loader — UNCHANGED
    
    def run(self):
        for event in self.node:
            if event["type"] == "INPUT":
                self.on_input(event)
            elif event["type"] == "STOP":
                break
    
    def on_input(self, event):
        # Parse pointcloud from raw bytes — same layout as ROS2 PointCloud2
        data = event["value"].to_numpy().view(np.uint8)
        points = parse_pointcloud_bytes(data)  # Your existing parser — UNCHANGED
        
        # Run algorithm — EXACT same call as ROS2 node
        pose = self.ndt_align(points)  # Your existing algorithm — UNCHANGED
        
        # Serialize pose to JSON for downstream nodes
        pose_json = json.dumps({
            "pose": {
                "position": {"x": pose.x, "y": pose.y, "z": pose.z},
                "orientation": {"x": pose.qx, "y": pose.qy, "z": pose.qz, "w": pose.qw}
            }
        })
        self.node.send_output("pose", pa.array([pose_json]))

if __name__ == "__main__":
    node = LocalizerNode()
    node.run()
```

### 6.3 Dataflow YAML

**File:** `dataflows/localization.yml`

```yaml
nodes:
  # LiDAR driver (Python node)
  - id: lidar_driver
    path: src/sensing/lidar_node/lidar_node.py
    inputs:
      tick: dora/timer/millis/100
    outputs:
      - pointcloud

  # Localizer (Python node)
  - id: localizer
    path: src/localization/localizer_node/localizer_node.py
    inputs:
      pointcloud: lidar_driver/pointcloud
    outputs:
      - pose
    env:
      MAP_PATH: /data/maps/current.pcd

  # ROS2 bridge (Python operator)
  - id: pose_bridge
    operator:
      python: src/localization/operators/pose_to_ros2.py
      inputs:
        pose: localizer/pose
```

### 6.4 Migration Takeaway

> **Algorithm code is untouched.** The only changes are:
> 1. Replace `rclpy.Node` with `dora.Node`
> 2. Replace `create_subscription()` with `for event in self.node:`
> 3. Replace `publish()` with `self.node.send_output()`
> 4. Replace ROS2 msg serialization with PyArrow arrays or JSON strings

This is a **wrapper migration**, not a rewrite. No C++ needed.

---

## 7. Migration Pattern: ROS2 Parameters → DORA Environment/Params

### 7.1 VisionPilot Parameters

```python
# ROS2 parameter declaration
self.declare_parameters(namespace='', parameters=[
    ('model_path', '/data/models/driving_vision.rknn'),
    ('inference_rate_hz', 20.0),
    ('npu_core_id', 0),
    ('debug', False),
])

# Usage
model_path = self.get_parameter('model_path').value
```

### 7.2 DORA Parameters

```yaml
# In dataflow.yml
nodes:
  - id: driving_vision
    custom:
      source: build/driving_vision_node
      inputs:
        image: image_preprocess/image_processed
      outputs:
        - features
    env:
      MODEL_PATH: /data/models/driving_vision_rk3688.rknn
      INFERENCE_RATE_HZ: "20"
      NPU_CORE_ID: "0"
      DEBUG: "false"
```

```python
# In node code
import os

model_path = os.environ.get("MODEL_PATH", "/data/models/default.rknn")
npu_core = int(os.environ.get("NPU_CORE_ID", "0"))
```

**For runtime parameter updates:** DORA supports `dora param set <node> <key> <value>` but this is best-effort. For safety-critical parameters, use YAML + restart.

---

## 8. Build System Migration

### 8.1 VisionPilot Build (colcon)

```bash
cd ~/visionpilot_ws
colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release
source install/setup.bash
```

### 8.2 DoraPilot Build

**Python nodes:** No build needed. DORA runs them directly.

```bash
# Install DORA CLI and Python API
cargo install dora-cli
pip install dora-rs numpy pyarrow

# Run dataflow (DORA handles Python deps automatically)
cd ~/dorapilot
dora run dataflows/dorapilot_main.yml
```

**No colcon, no CMake, no package.xml, no setup.py, no C++ compilation** for DORA-native components. Pure Python + YAML.

---

## 9. Testing Migration: rosbag → dora record/replay

### 9.1 VisionPilot Testing

```bash
# Record
ros2 bag record /sensing/camera/image_raw /sensing/lidar/points

# Replay (cannot substitute nodes)
ros2 bag play bag_file/
```

### 9.2 DoraPilot Testing

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

Use this checklist for each node migration:

- [ ] **Identify node type**: Operator (lightweight) or Custom Node (heavy compute/isolation)?
- [ ] **Copy algorithm code**: Reuse Python implementation unchanged
- [ ] **Replace ROS2 imports**: Remove `rclpy`, `std_msgs`, `sensor_msgs`
- [ ] **Add DORA imports**: `from dora import DoraStatus` or `from dora import Node`
- [ ] **Replace init**: `rclpy.init()` → DORA runtime init (implicit for operators, `Node()` for Python nodes)
- [ ] **Replace subscribers**: `create_subscription()` → `on_input()` method or `for event in node:` loop
- [ ] **Replace publishers**: `create_publisher()` + `publish()` → `send_output()`
- [ ] **Replace timers**: `create_timer()` → `dora/timer/millis/N` in YAML
- [ ] **Replace parameters**: `declare_parameter()` → `os.environ.get()` from YAML `env:`
- [ ] **Serialize data**: ROS2 msgs → PyArrow arrays or raw bytes
- [ ] **Add to dataflow.yml**: Declare node ID, inputs, outputs, env
- [ ] **Test standalone**: `dora run dataflows/test.yml` with just this node
- [ ] **Validate timing**: `dora topic hz <node>/<output>`

---

## References

| Project | Path | What to Learn |
|---------|------|---------------|
| **dora-autoware.universe** | `~/pilot/autoware.universe` | Full Autoware port to DORA — NDT, EKF, GNSS, IMU, YOLO (Python API) |
| **YOLO operator** | `perception/yolo/object_detection_yolov5.py` | Python operator pattern for ML inference |
| **Camera operator** | `dora-hardware/vendors/camera/OpenCV/webcam.py` | Image capture → PyArrow array |
| **LiDAR node** | `sensing/lidar_node/lidar_node.py` | Pandar QT64 capture → PyArrow bytes (DORA-native) |
| **Pose bridge** | `localization/ndt_localizer/pose_to_ros2.py` | DORA → ROS2 bridge pattern (Python) |
| **Dataflow examples** | `dataflows/dorapilot_main.yml` | YAML syntax for Python nodes and operators |

---

*Migration guide v1.0 — 2026-05-30*
