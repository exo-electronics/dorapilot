# DoraPilot Development Guide

**For developers joining the project.**

This guide covers: writing nodes, defining messages, running dataflows, and debugging.

---

## Table of Contents

1. [Environment Setup](#environment-setup)
2. [Project Layout](#project-layout)
3. [Writing a Node](#writing-a-node)
4. [Writing an Operator](#writing-an-operator)
5. [Using drp_msgs](#using-drp_msgs)
6. [Dataflow YAML](#dataflow-yaml)
7. [Running and Debugging](#running-and-debugging)
8. [Porting from VisionPilot](#porting-from-visionpilot)
9. [Common Patterns](#common-patterns)

---

## Environment Setup

```bash
# 1. Clone
git clone git@github.com:exo-electronics/dorapilot.git
cd dorapilot

# 2. Install DORA
pip install dora-rs numpy pyarrow

# 3. Verify
dora --version   # should show 1.0+
dora validate dataflows/dorapilot_main.yml
```

**No colcon. No CMake. No ROS2 sourcing required.**

---

## Project Layout

```
src/
├── drp_msgs/              # Messages (import these, never ROS2 msgs)
├── sensing/               # Camera, LiDAR, GNSS, IMU
├── perception/            # NPU inference + fusion
├── planning/              # Behavior + MPC trajectory
├── control/               # 100Hz PID
├── safety/                # AEB, FCW, MRM
├── system/                # Inference daemon, camera daemon
└── vehicle_bridge/        # ROS2 bridge (vehicle boundary only)
```

**Rule:** Application code lives in `src/`. No C++. No CMake.

---

## Writing a Node

A **node** is a standalone Python process. Use nodes for:
- NPU inference (crash must not affect other nodes)
- Heavy compute (MPC solver)
- Safety-critical code (AEB)

### Template

```python
#!/usr/bin/env python3
"""My node — one-line description."""

from dora import Node
from drp_msgs import Header, MyInputMsg, MyOutputMsg
from drp_msgs.utils import to_arrow, from_arrow


class MyNode:
    def __init__(self):
        self.node = Node()
        # Load models, initialize state
        self.model = self._load_model()

    def _load_model(self):
        """Load RKNN model or other resources."""
        return None

    def on_input(self, event):
        """Handle incoming data."""
        # Deserialize from Arrow
        msg = from_arrow(event["value"], MyInputMsg)

        # Process
        result = self._process(msg)

        # Serialize to Arrow and send
        self.node.send_output("result", to_arrow(result))

    def _process(self, msg: MyInputMsg) -> MyOutputMsg:
        """Your algorithm here."""
        return MyOutputMsg(header=msg.header, data=msg.data * 2)

    def run(self):
        """Main loop — do not modify."""
        for event in self.node:
            if event["type"] == "INPUT":
                self.on_input(event)
            elif event["type"] == "STOP":
                break


if __name__ == "__main__":
    MyNode().run()
```

### Add to Dataflow

```yaml
nodes:
  - id: my_node
    path: src/perception/my_node/my_node.py
    inputs:
      input_data: upstream_node/output_name
    outputs:
      - result
    env:
      MODEL_PATH: /data/models/my_model.rknn
      PARAM: "42"
    restart_policy: on_failure
    max_restarts: 3
```

### Key Rules

- **Always use `from_arrow()` / `to_arrow()`** — never manual `json.loads()`
- **Always specify message type** — `from_arrow(event["value"], PerceptionContext)`
- **Never import ROS2** — `from sensor_msgs.msg import Image` is forbidden in DORA-native nodes
- **Environment via `self.node.env`** — not `os.environ` directly

---

## Writing an Operator

An **operator** runs in-process inside the DORA runtime. Use operators for:
- Lightweight transforms (crop, resize, filter)
- Low-latency loops (100Hz PID)
- Stateless computations

### Template

```python
#!/usr/bin/env python3
"""My operator — one-line description."""

from dora import DoraStatus
from drp_msgs import PointCloud2
from drp_msgs.utils import to_arrow, from_arrow


class Operator:
    def __init__(self):
        # Read env from dataflow YAML
        self.voxel_size = 0.1

    def on_event(self, dora_event, send_output) -> DoraStatus:
        if dora_event["type"] == "INPUT":
            return self.on_input(dora_event, send_output)
        return DoraStatus.CONTINUE

    def on_input(self, dora_input, send_output):
        """Handle input and emit output."""
        msg = from_arrow(dora_input["value"], PointCloud2)
        points = msg.to_numpy()

        # Process (numpy-vectorized = C speed)
        filtered = points[points[:, 2] > -3.0]  # Remove ground points

        # Send output
        result = PointCloud2.from_xyz_array(filtered, header=msg.header)
        send_output("filtered", to_arrow(result))

        return DoraStatus.CONTINUE
```

### Add to Dataflow

```yaml
nodes:
  - id: my_operator
    operators:
      python: src/sensing/operators/my_operator.py
    inputs:
      pointcloud: lidar/pointcloud
    outputs:
      - filtered
```

### Node vs Operator: When to Use What

| | Node | Operator |
|--|------|----------|
| **Process** | Standalone | In-process |
| **Crash isolation** | ✅ Yes | ❌ No (crashes runtime) |
| **Latency** | ~0.1ms SHM overhead | ~10µs function call |
| **Use for** | NPU, MPC, safety | Preprocess, PID, filter |
| **Example** | `driving_vision` | `image_preprocess` |

---

## Using drp_msgs

### Import Messages

```python
from drp_msgs import (
    Header, Time,
    Point, Quaternion, Pose, PoseStamped,
    Image, PointCloud2, Imu, NavSatFix,
    PerceptionContext, DetectedObjectArray, LeadVehicle,
    Trajectory, ManeuverCommand,
    LateralCommand, LongitudinalCommand,
    VehicleState, VehicleCommand,
)
```

### Create and Send

```python
from drp_msgs import Header, PointCloud2
from drp_msgs.utils import to_arrow
import numpy as np

# Create PointCloud2 from numpy array
points = np.random.rand(1000, 4).astype(np.float32)  # x, y, z, intensity
pc2 = PointCloud2.from_xyz_array(points, header=Header(frame_id="lidar"))

# Send through DORA
self.node.send_output("pointcloud", to_arrow(pc2))
```

### Receive and Parse

```python
from drp_msgs import PointCloud2
from drp_msgs.utils import from_arrow

# In on_input()
pc2 = from_arrow(event["value"], PointCloud2)
points = pc2.to_numpy()          # Nx4 float32 array
print(f"Received {len(points)} points from {pc2.header.frame_id}")
```

### Convert to ROS2 (for Bridge Nodes Only)

```python
# Only in vehicle_bridge/ or ros2_bridge/ nodes
ros2_dict = pc2.to_dict()  # ROS2-compatible dict
# Publish via dora.experimental.ros2_bridge
```

### Add a New Message Type

1. Open the appropriate module (e.g., `src/drp_msgs/perception_msgs.py`)
2. Add a `@dataclass` with `to_dict()` and `from_dict()` methods
3. Export from `src/drp_msgs/__init__.py`
4. Done — no compilation, no rebuild

```python
# src/drp_msgs/perception_msgs.py
@dataclass
class MyNewMessage:
    header: Header
    value: np.float32

    def to_dict(self) -> dict:
        return {"header": self.header.to_dict(), "value": float(self.value)}

    @classmethod
    def from_dict(cls, d: dict) -> "MyNewMessage":
        return cls(header=Header.from_dict(d["header"]), value=np.float32(d["value"]))
```

---

## Dataflow YAML

### Minimal Example

```yaml
nodes:
  - id: camera
    path: src/sensing/camera/camera_node.py
    inputs:
      tick: dora/timer/millis/33   # 30Hz timer
    outputs:
      - image_raw

  - id: processor
    operators:
      python: src/sensing/operators/image_preprocess.py
    inputs:
      image: camera/image_raw
    outputs:
      - image_processed

  - id: detector
    path: src/perception/driving_vision/driving_vision_node.py
    inputs:
      image: processor/image_processed
    outputs:
      - features
```

### Reference

| Key | Description | Example |
|-----|-------------|---------|
| `id` | Unique node identifier | `driving_vision` |
| `path` | Python script for standalone node | `src/perception/dv/dv.py` |
| `operators.python` | Python file for in-process operator | `src/sensing/operators/crop.py` |
| `inputs.<name>` | Input source (`node_id/output_id`) | `camera/image_raw` |
| `outputs` | List of output names | `[features, engagement]` |
| `env` | Environment variables | `MODEL_PATH: /data/model.rknn` |
| `restart_policy` | `on_failure`, `always`, `never` | `on_failure` |
| `max_restarts` | Max auto-restarts | `3` |
| `cpu_affinity` | Pin to CPU cores | `[4, 5]` |
| `input_timeout` | Circuit breaker | `image: 100ms` |

### Validate Before Running

```bash
dora validate dataflows/dorapilot_main.yml
# Shows: missing inputs, disconnected nodes, syntax errors
```

---

## Running and Debugging

### Development Loop

```bash
# 1. Edit your node
nano src/perception/my_node/my_node.py

# 2. Validate dataflow
dora validate dataflows/dorapilot_main.yml

# 3. Run (no build, no wait)
dora run dataflows/dorapilot_main.yml --verbose

# 4. In another terminal, monitor
dora top
dora topic hz my_node/result
```

### Debug a Single Node

```bash
# Run only one node with mock inputs
dora run dataflows/dorapilot_main.yml --node my_node --verbose
```

### Record and Replay

```bash
# Record sensor data
dora record dataflows/dorapilot_main.yml --output test_drive.drec

# Replay with a modified node
dora replay test_drive.drc \
  --substitute my_node:my_node_v2.py \
  --speed 2.0
```

### Common Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ModuleNotFoundError: drp_msgs` | Not in PYTHONPATH | `export PYTHONPATH=$PWD/src:$PYTHONPATH` |
| `KeyError: 'value'` | Used `event["value"]` on STOP event | Check `event["type"]` first |
| `dora: command not found` | DORA CLI not installed | `pip install dora-rs` |
| Node restarts endlessly | `restart_policy: on_failure` + bug | Check logs: `dora logs <dataflow> <node>` |

---

## Porting from VisionPilot

### Checklist for Each Node

- [ ] **Copy Python algorithm code** from VisionPilot (unchanged)
- [ ] **Replace ROS2 imports**: Remove `rclpy`, `sensor_msgs`, `cv_bridge`
- [ ] **Add DORA imports**: `from dora import Node` or `from dora import DoraStatus`
- [ ] **Add drp_msgs imports**: `from drp_msgs import X` (map from `evp_msgs.msg`)
- [ ] **Replace subscribers**: `create_subscription()` → `for event in node:` loop
- [ ] **Replace publishers**: `create_publisher()` + `publish()` → `send_output()`
- [ ] **Replace timers**: `create_timer()` → `dora/timer/millis/N` in YAML
- [ ] **Replace parameters**: `declare_parameter()` → `self.node.env.get()`
- [ ] **Serialize data**: `evp_msgs` → `to_arrow()` / `from_arrow()`
- [ ] **Add to dataflow.yml**: Declare node ID, inputs, outputs
- [ ] **Test standalone**: `dora run dataflows/test.yml` with just this node

### Message Mapping: evp_msgs → drp_msgs

| VisionPilot (evp_msgs) | Dorapilot (drp_msgs) |
|------------------------|----------------------|
| `evp_msgs.msg.EgoState` | `drp_msgs.perception_msgs.PerceptionContext` |
| `evp_msgs.msg.DetectedObjectArray` | `drp_msgs.perception_msgs.DetectedObjectArray` |
| `evp_msgs.msg.NeuralPath` | `drp_msgs.planning_msgs.Trajectory` |
| `evp_msgs.msg.ControlCommand` | `drp_msgs.vehicle_msgs.VehicleCommand` |
| `std_msgs.msg.Header` | `drp_msgs.std_msgs.Header` |
| `sensor_msgs.msg.Image` | `drp_msgs.sensor_msgs.Image` |
| `sensor_msgs.msg.PointCloud2` | `drp_msgs.sensor_msgs.PointCloud2` |

---

## Common Patterns

### Pattern: NPU Inference Node

```python
class NPUInferenceNode:
    def __init__(self):
        self.node = Node()
        model_path = self.node.env.get("MODEL_PATH")
        core = int(self.node.env.get("NPU_CORE", 0))
        self.model = load_rknn(model_path, core)

    def on_input(self, event):
        image = from_arrow(event["value"], Image)
        arr = image.to_numpy()
        outputs = self.model.infer(arr)
        self.node.send_output("result", to_arrow(outputs))
```

### Pattern: Timer-Based Sensing Node

```python
class CameraNode:
    def __init__(self):
        self.node = Node()
        self.camera = open_camera(self.node.env.get("CAMERA_DEVICE"))

    def on_input(self, event):
        # Triggered by tick: dora/timer/millis/33
        frame = self.camera.capture()
        image = Image.from_numpy(frame, header=Header(frame_id="camera"))
        self.node.send_output("image_raw", to_arrow(image))
```

### Pattern: Fusion Node (Multiple Inputs)

```python
class FusionNode:
    def __init__(self):
        self.node = Node()
        self.camera_data = None
        self.lidar_data = None

    def on_input(self, event):
        if event["id"] == "camera_objects":
            self.camera_data = from_arrow(event["value"], DetectedObjectArray)
        elif event["id"] == "lidar_objects":
            self.lidar_data = from_arrow(event["value"], DetectedObjectArray)

        if self.camera_data and self.lidar_data:
            fused = self.fuse(self.camera_data, self.lidar_data)
            self.node.send_output("fused_objects", to_arrow(fused))
```

### Pattern: Safety Node with Timeout

```yaml
nodes:
  - id: aeb
    path: src/safety/aeb/aeb_node.py
    inputs:
      perception_context: main/perception_context
    outputs:
      - emergency_brake_request
    restart_policy: never
    input_timeout:
      perception_context: 100ms  # Trigger if no data for 100ms
```

---

*DEVELOPMENT.md v1.0 — 2026-05-30*
