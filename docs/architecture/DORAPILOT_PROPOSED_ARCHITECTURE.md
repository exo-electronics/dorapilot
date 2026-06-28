# DoraPilot Proposed Architecture v2.0 — Hybrid Autoware + VisionPilot

**Date:** 2026-05-30  
**Status:** Active Development  
**Target:** ExoPilot 03 (RK3688), ExoPilot 04 (RKxxxx)  
**Middleware:** dora-rs 1.0 + ROS2 Humble (bridged at boundaries only)  
**Language:** Python 3.10+ for all application nodes  
**Baseline:** Autoware.universe DORA port (patterns) + VisionPilot (ADAS logic + models)

---

## Philosophy: Best of Both Worlds

| What We Take | From Where | Why |
|--------------|-----------|-----|
| **Directory structure** | Autoware.universe | Familiar to Autoware developers: `sensing/`, `perception/`, `planning/`, `control/` |
| **Message conventions** | ROS2 / Autoware | `Header`, `PoseStamped`, `PointCloud2`, `Twist` — industry standard |
| **LiDAR parsing patterns** | autoware.universe DORA port | Proven byte-parsing for pointclouds, ROS2 bridge |
| **ADAS logic** | VisionPilot | Engagement, lead vehicle, behavior planner — our proven product |
| **NPU models** | VisionPilot | `driving_vision`, `driving_policy`, `lane_detector` RKNN models |
| **MPC + PID control** | VisionPilot | 20Hz trajectory + 100Hz control — tuned for our vehicle |
| **Vehicle interface** | VisionPilot | CAN codec, DBC parser, calibrated for our platform |
| **Zero-copy IPC** | dora-rs | Apache Arrow + Zenoh SHM — 10-31× faster than ROS2 DDS |
| **Declarative pipelines** | dora-rs | `dataflow.yml` replaces nested launch files |

> **For Autoware developers:** The directory layout and message names are familiar. You already know where things live.
> **For VisionPilot developers:** Your Python logic and models are preserved. Only the middleware and packaging changes.

---

## Why DORA for DoraPilot (Successor to VisionPilot)

VisionPilot proved that a Python-centric ADAS stack can work on edge SoC. DoraPilot replaces ROS2 with **dora-rs** to solve the one problem Python+ROS2 cannot fix: **inter-process communication overhead on large payloads**.

| Pain Point in VisionPilot (ROS2) | DORA Solution | Impact on Dorapilot |
|-----------------------------------|---------------|---------------------|
| PointCloud2 serialization eats 15–20% CPU core just moving data | Zenoh SHM zero-copy: pointer pass, not data copy | More TOPS for inference, not IPC |
| 150 packages, nested Python launch files, scattered param YAMLs | Single `dataflow.yml` declares entire pipeline | Onboard debugging in minutes, not hours |
| A/B test requires full system restart | `dora node add/disconnect` at runtime | Parallel model evaluation without reboot |
| ROS2 bags: no node substitution for regression testing | `.drec` record/replay with `--substitute` | Same sensor inputs, different algorithms |
| `ros2 topic hz` + external Prometheus for observability | `dora top`, `dora trace view` built-in | Production observability out of the box |
| GIL contention + CDR deserialization in Python nodes | Apache Arrow format: zero deserialization overhead | Python nodes run at full speed |

**The LiDAR imperative:** Pandar QT64 produces ~200,000 points/frame ≈ 2–3 MB at 10 Hz. In ROS2, this payload balloons latency to 5–15 ms with jitter. In DORA, it is a **shared memory pointer pass** — <1 ms, flat. This is not incremental; it is transformative for real-time fusion.

---

## What Changes from VisionPilot

### Architecture Changes

| Aspect | VisionPilot (ROS2) | DoraPilot (DORA) |
|--------|-------------------|------------------|
| **Directory layout** | Flat package list (150+ pkgs) | Autoware-style hierarchy (`sensing/`, `perception/`, `planning/`, `control/`) |
| **IPC mechanism** | DDS CDR serialization | Zenoh SHM zero-copy (Apache Arrow) |
| **Pipeline definition** | Python launch files + param YAML | Declarative `dataflow.yml` |
| **Build system** | colcon + CMake + package.xml | `pip install dora-rs` — no build for app code |
| **Node language** | Python + C++ wrappers (mixed) | **Python only** |
| **Message format** | ROS2 `.msg` IDL → CDR | **drp_msgs** (Python dataclasses → Arrow) |
| **Message compilation** | `rosidl` generates C++/Python | Zero compilation — import and use |
| **Record/replay** | MCAP bag (no substitution) | `.drec` native + node substitution |
| **Observability** | External tooling required | `dora top`, `dora trace` built-in |

### What Stays the Same

- **Python application code** — all inference, planning, control logic stays Python
- **ACADOS solver** — same Python interface (`gen_long_mpc.py` + generated C solver binary)
- **RKNN/Hailo models** — same `.rknn`/`.hef` files, same inference daemon pattern
- **3-layer boundary** (App / System / Third_Party) — preserved
- **Functional naming** (`npu_rockchip`, `dmu_rga`) — preserved
- **Daemon pattern** (`camera_daemon`, `thermal_daemon`) — preserved as DORA nodes
- **MPC + PID two-layer control** (20Hz + 100Hz) — preserved
- **Budget-based NPU allocation** (85% TOPS safety line) — preserved

---

## Best Practices from dora-autoware (Ported Experience)

The **dora-autoware** project (github.com/dora-rs/dora-autoware) ported Autoware.universe modules to DORA. Key lessons for dorapilot:

### 1. Keep LiDAR Pipeline 100% DORA-Native
The dora-autoware team hit a **blocker** with the ROS2 bridge: PointCloud2 struct arrays panic the Arrow↔ROS2 converter (`"Struct array's data type is not struct!"`). Their fix: **never bridge PointCloud2**. Dorapilot follows this rule strictly.

### 2. Parse Raw Bytes in Python (No C++ Parser Needed)
Autoware's NDT localization was ported to DORA using the **Python API** with numpy byte parsing:
```python
# Direct byte layout parsing — same performance as C++ for this workload
data = event["value"].to_numpy().view(np.uint8)
points = np.frombuffer(data, dtype=np.float32).reshape(-1, 4)
```
This eliminates the need for a C++ parsing node. The Python GIL is not a bottleneck here because the work is numpy-vectorized (C underneath).

### 3. Use Operators for Preprocessing, Nodes for Compute
Dora-autoware's dataflow pattern:
- **Operators**: crop, resize, format convert, voxel filter (in-process, zero overhead)
- **Nodes**: NPU inference, localization, planning (isolated process, crash-safe)

### 4. Separate Safety Dataflow
Autoware's safety modules run in an **independent dataflow** so a main pipeline restart does not affect AEB/MRM. Dorapilot adopts this: `dorapilot_safety.yml` is separate from `dorapilot_main.yml`.

### 5. Python-First, No Shame in Python
The dora-autoware port uses the **Python API** for the majority of nodes. The Rust core handles IPC; application logic stays in Python. This is the intended pattern — not a workaround.

---

## Design Principles

1. **DORA-native for data-heavy pipelines** — sensing, perception, planning use zero-copy Zenoh SHM
2. **ROS2 bridge at the boundaries** — vehicle interface, voice, navigation remain ROS2 for ecosystem compatibility
3. **Python-only for application code** — all nodes and operators written in Python 3.10+. No C++ nodes, no CMake, no package.xml for DORA-native components.
4. **Autoware directory conventions** — `sensing/`, `perception/`, `planning/`, `control/` for developer familiarity
5. **drp_msgs for type safety** — pure-Python dataclasses with ROS2-compatible naming, zero compilation
6. **Operators for lightweight transforms, Nodes for heavy compute** — minimize process overhead where safe
7. **Safety-critical isolation** — AEB/FCW/MRM run as dedicated nodes with `restart_policy: never`
8. **Declarative everything** — `dataflow.yml` defines the pipeline, not Python launch files
9. **No serialization tax on LiDAR** — PointCloud2 stays in DORA-native Arrow format; never bridges to ROS2

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DoraPilot v2.0 — Hybrid Stack                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    DORA DATAFLOW (Zero-Copy SHM)                     │   │
│  │                                                                      │   │
│  │  SENSING              PERCEPTION           PLANNING        CONTROL   │   │
│  │  ────────             ──────────           ────────        ───────   │   │
│  │  camera         ──► driving_vision  ──► behavior_planner ──►       │   │
│  │       │                │                     │              controller│   │
│  │       │                │                     │                 │     │   │
│  │  lidar ─────────► lidar_detector ───► trajectory_planner ──►       │   │
│  │       │                │                     │                 │     │   │
│  │       │                ▼                     ▼                 ▼     │   │
│  │       └──► perception_fusion ──────────► trajectory_selector       │   │
│  │                      (PerceptionContext)                             │   │
│  │                                                                      │   │
│  │  OPERATORS: image_preprocess, pointcloud_filter                      │   │
│  │                                                                      │   │
│  └──────────────────────────────┬──────────────────────────────────────┘   │
│                                 │                                           │
│                                 ▼ ROS2 Bridge                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    ROS2 ECOSYSTEM (Boundary Layer)                   │   │
│  │                                                                      │   │
│  │  Vehicle Interface    CAN Driver    Dashboard    Voice    Navigation │   │
│  │  ─────────────────    ─────────    ──────────    ─────    ────────── │   │
│  │  vehicle_bridge ────► can_driver    ui_node     whisper   valhalla  │   │
│  │       │                                                            │   │
│  │       ▼                                                            │   │
│  │   CAN Frames → Vehicle                                             │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    SYSTEM DAEMONS (DORA + ROS2)                      │   │
│  │                                                                      │   │
│  │  inference_daemon    camera_daemon    thermal_daemon    health_daemon│   │
│  │       │                  │                 │                │        │   │
│  │       ▼                  ▼                 ▼                ▼        │   │
│  │   NPU/GPU/RGA       V4L2/ISP         Thermal zones    Diagnostics   │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## drp_msgs — The Message System

### Why Not ROS2 .msg Files?

| ROS2 `.msg` | drp_msgs (Python) |
|-------------|-------------------|
| Requires `rosidl` + CMake + package.xml | Pure Python, zero compilation |
| IDL compilation step | Import and use immediately |
| C++ header generation | Not needed (Python-only stack) |
| No autocomplete in editors | Full IDE autocomplete |

### Why Not Raw Python Dicts?

| Raw `dict` | drp_msgs dataclass |
|------------|-------------------|
| `data["engagemnt"]` → silent KeyError | `msg.engagement` → autocomplete + typo catching |
| No field documentation | Docstrings on every field |
| No unit conventions | Enforced suffixes (`_m`, `_mps`, `_rad`) |
| Schema drift between nodes | Single source of truth in `src/drp_msgs/` |

### For Autoware Developers

```python
from drp_msgs import Header, PointCloud2, PoseStamped, PerceptionContext
from drp_msgs.utils import to_arrow, from_arrow

# Create message (identical API to ROS2)
msg = PerceptionContext(
    header=Header(frame_id="base_link"),
    engagement=True,
    lead=LeadVehicle(distance_m=45.2, velocity_mps=15.0)
)

# Send through DORA (zero-copy Arrow)
node.send_output("context", to_arrow(msg))

# Receive from DORA
event = node.next()
ctx = from_arrow(event["value"], PerceptionContext)
print(ctx.lead.distance_m)  # 45.2 — IDE autocomplete works

# Bridge to ROS2 (when needed)
ros2_dict = msg.to_dict()
publisher.publish(pa.array([ros2_dict]))
```

### Message Hierarchy

```
drp_msgs/
├── std_msgs.py        # Header, Time, String, Bool, Float32/64, Int32/64, UInt32/64
├── geometry_msgs.py   # Point, Quaternion, Pose, PoseStamped, Twist, Vector3, Transform
├── sensor_msgs.py     # Image, PointCloud2, PointField, Imu, NavSatFix
├── nav_msgs.py        # Path, Odometry
├── perception_msgs.py # PerceptionContext, DetectedObject, LeadVehicle, LaneLine, TrafficLight
├── planning_msgs.py   # Trajectory, TrajectoryPoint, ManeuverCommand
├── control_msgs.py    # LateralCommand, LongitudinalCommand
├── vehicle_msgs.py    # VehicleState, VehicleCommand, GearShift
├── safety_msgs.py     # EmergencyBrakeRequest, FCWEvent, MRMManeuver
└── utils.py           # to_arrow(), from_arrow(), to_ros2_msg(), from_ros2_msg()
```

### Key Message: PerceptionContext

Replaces VisionPilot's scattered ROS2 topics with **one structured message**:

```python
@dataclass
class PerceptionContext:
    header: Header
    engagement: bool
    lead: Optional[LeadVehicle]
    lane_lines: LaneLineArray
    objects_3d: DetectedObjectArray
    traffic_lights: TrafficLightArray
    safety_events: List[str]
    speed_limit_mps: np.float32
    road_condition: str
```

Sent by `perception_fusion` at 20Hz. Consumed by `behavior_planner`, `trajectory_planner`, and safety nodes.

---

## Dataflow Definition

### Main Pipeline (`dataflows/dorapilot_main.yml`)

```yaml
# DoraPilot Main Dataflow — Hybrid Autoware + VisionPilot Architecture
# ALL nodes are Python. No C++ nodes, no CMake.
#
# For Autoware developers:
#   - Directory structure follows autoware.universe
#   - Messages use drp_msgs (ROS2-compatible pure Python)
#   - Dataflow patterns adapted from autoware.universe DORA port
#
# For VisionPilot developers:
#   - Node logic preserved (driving_vision, driving_policy, behavior_planner)
#   - ACADOS MPC trajectory planner preserved
#   - PID controller preserved

nodes:
  # ─── SENSING (Autoware-style hierarchy) ───
  - id: camera
    path: src/sensing/camera/camera_node.py
    inputs:
      tick: dora/timer/millis/33
    outputs: [image_raw]
    env:
      CAMERA_DEVICE: /dev/video0
      WIDTH: "1920"
      HEIGHT: "1080"
      FORMAT: nv12

  - id: lidar
    path: src/sensing/lidar/lidar_node.py
    inputs:
      tick: dora/timer/millis/100
    outputs: [pointcloud]
    env:
      LIDAR_MODEL: pandar_qt64
      LIDAR_IP: "192.168.1.201"

  - id: gnss
    path: src/sensing/gnss/gnss_node.py
    inputs:
      tick: dora/timer/millis/100
    outputs: [navsatfix]

  - id: imu
    path: src/sensing/imu/imu_node.py
    inputs:
      tick: dora/timer/millis/10
    outputs: [imu_data]

  # ─── PREPROCESSING (Operators for zero-overhead) ───
  - id: image_preprocess
    operators:
      python: src/sensing/operators/image_preprocess.py
    inputs:
      image_raw: camera/image_raw
    outputs: [image_resized, image_yuv]
    env:
      RESIZE_WIDTH: "512"
      RESIZE_HEIGHT: "256"
      USE_RGA: "true"

  - id: pointcloud_filter
    operators:
      python: src/sensing/operators/pointcloud_filter.py
    inputs:
      pointcloud: lidar/pointcloud
    outputs: [points_filtered]
    env:
      VOXEL_SIZE: "0.1"
      CROP_BOX_MIN: "[-50, -25, -3]"
      CROP_BOX_MAX: "[50, 25, 1]"

  # ─── PERCEPTION (VisionPilot models + Autoware structure) ───
  - id: driving_vision
    path: src/perception/driving_vision/driving_vision_node.py
    inputs:
      image: image_preprocess/image_yuv
    outputs: [features, engagement]
    env:
      MODEL_PATH: /data/models/driving_vision_rk3688.rknn
      NPU_CORE: "0"
    restart_policy: on_failure
    max_restarts: 3

  - id: driving_policy
    path: src/perception/driving_policy/driving_policy_node.py
    inputs:
      features: driving_vision/features
      vehicle_state: vehicle_bridge/vehicle_state
    outputs: [neural_path, leads]
    env:
      MODEL_PATH: /data/models/driving_policy_rk3688.rknn
      NPU_CORE: "0"
    restart_policy: on_failure
    max_restarts: 3

  - id: lane_detector
    path: src/perception/lane_detector/lane_detector_node.py
    inputs:
      image: image_preprocess/image_resized
    outputs: [lane_lines]
    env:
      MODEL_PATH: /data/models/lane_detector_rk3688.rknn
      NPU_CORE: "1"

  - id: lidar_detector
    path: src/perception/lidar_detector/lidar_detector_node.py
    inputs:
      pointcloud: pointcloud_filter/points_filtered
    outputs: [objects_3d]
    env:
      MODEL_PATH: /data/models/pointpillars_rk3688.rknn
      NPU_CORE: "1"

  - id: traffic_light_detector
    path: src/perception/traffic_light_detector/traffic_light_detector_node.py
    inputs:
      image: image_preprocess/image_resized
    outputs: [traffic_lights]
    env:
      MODEL_PATH: /data/models/traffic_light_rk3688.rknn
      NPU_CORE: "1"

  # ─── PERCEPTION FUSION (unified PerceptionContext) ───
  - id: perception_fusion
    path: src/perception/perception_fusion/perception_fusion_node.py
    inputs:
      camera_objects: driving_policy/leads
      objects_3d: lidar_detector/objects_3d
      lane_lines: lane_detector/lane_lines
      traffic_lights: traffic_light_detector/traffic_lights
      gnss_fix: gnss/navsatfix
      imu_raw: imu/imu_data
    outputs: [perception_context]
    env:
      FUSION_RATE: "20"

  # ─── PLANNING (VisionPilot MPC + Autoware behavior) ───
  - id: behavior_planner
    path: src/planning/behavior_planner/behavior_planner_node.py
    inputs:
      perception_context: perception_fusion/perception_context
    outputs: [maneuver_command]
    env:
      PLANNING_RATE: "20"

  - id: trajectory_planner
    path: src/planning/trajectory_planner/trajectory_planner_node.py
    inputs:
      maneuver: behavior_planner/maneuver_command
      perception_context: perception_fusion/perception_context
    outputs: [trajectory]
    env:
      MPC_HORIZON: "20"
      MPC_DT: "0.05"
      SOLVER: acados
    cpu_affinity: [4, 5]

  - id: trajectory_selector
    path: src/planning/trajectory_selector/trajectory_selector_node.py
    inputs:
      neural_trajectory: trajectory_planner/trajectory
      classical_trajectory: auto_speed/classical_path
    outputs: [selected_trajectory]
    env:
      SELECTOR_MODE: safety_first

  # ─── CONTROL (100Hz PID — VisionPilot proven) ───
  - id: controller
    path: src/control/controller/controller_node.py
    inputs:
      trajectory: trajectory_selector/selected_trajectory
      vehicle_state: vehicle_bridge/vehicle_state
    outputs: [lateral_cmd, longitudinal_cmd]
    env:
      CONTROL_RATE: "100"
      LATERAL_MODE: torque_pid
      LONGITUDINAL_MODE: openpid
    cpu_affinity: [6, 7]
    restart_policy: never

  # ─── ROS2 BRIDGE (Vehicle boundary — adapted from autoware) ───
  - id: vehicle_bridge
    path: src/vehicle_bridge/vehicle_bridge_node.py
    inputs:
      lateral_cmd: controller/lateral_cmd
      longitudinal_cmd: controller/longitudinal_cmd
    outputs: [vehicle_state]
    env:
      ROS2_DOMAIN_ID: "0"
      VEHICLE_CAN_INTERFACE: can0
      DBC_PATH: /data/dbc/vehicle.dbc
```

### Safety Dataflow (`dataflows/dorapilot_safety.yml`)

```yaml
# Independent safety dataflow — can survive main dataflow restart
nodes:
  - id: aeb
    path: src/safety/aeb/aeb_node.py
    inputs:
      perception_context: main/perception_context
      vehicle_state: vehicle_bridge/vehicle_state
    outputs: [emergency_brake_request]
    restart_policy: never
    input_timeout:
      perception_context: 100ms

  - id: fcw
    path: src/safety/fcw/fcw_node.py
    inputs:
      perception_context: main/perception_context
    outputs: [forward_collision_warning]
    restart_policy: never

  - id: mrm_handler
    path: src/safety/mrm/mrm_handler_node.py
    inputs:
      emergency_brake: aeb/emergency_brake_request
      fcw: fcw/forward_collision_warning
      system_health: health_daemon/status
    outputs: [mrm_command]
    restart_policy: never
```

---

## Directory Structure

```
dorapilot/
├── AGENTS.md                              # Agent instructions
├── README.md                              # Project overview
├── dataflows/
│   ├── dorapilot_main.yml                 # Main ADAS pipeline
│   ├── dorapilot_safety.yml               # Isolated safety dataflow
│   └── modules/                           # Reusable sub-graphs
├── docs/
│   ├── research/
│   │   ├── DORA_MIGRATION_RESEARCH.md     # Migration strategy
│   │   ├── DORA_PROS_CONS.md              # Comparative analysis
│   │   └── VISIONPILOT_TO_DORA_MIGRATION_GUIDE.md
│   └── architecture/
│       └── DORAPILOT_PROPOSED_ARCHITECTURE.md  # This file
├── src/                                   # ALL Python application code
│   ├── drp_msgs/                          # Message definitions (ROS2-compatible)
│   │   ├── __init__.py
│   │   ├── std_msgs.py
│   │   ├── geometry_msgs.py
│   │   ├── sensor_msgs.py
│   │   ├── nav_msgs.py
│   │   ├── perception_msgs.py
│   │   ├── planning_msgs.py
│   │   ├── control_msgs.py
│   │   ├── vehicle_msgs.py
│   │   ├── safety_msgs.py
│   │   └── utils.py
│   ├── sensing/                           # Autoware-style hierarchy
│   │   ├── camera/
│   │   │   └── camera_node.py
│   │   ├── lidar/
│   │   │   └── lidar_node.py             # Pandar QT64, byte parsing
│   │   ├── gnss/
│   │   │   └── gnss_node.py
│   │   ├── imu/
│   │   │   └── imu_node.py
│   │   └── operators/
│   │       ├── image_preprocess.py
│   │       └── pointcloud_filter.py
│   ├── perception/
│   │   ├── driving_vision/
│   │   │   └── driving_vision_node.py
│   │   ├── driving_policy/
│   │   │   └── driving_policy_node.py
│   │   ├── lane_detector/
│   │   │   └── lane_detector_node.py
│   │   ├── lidar_detector/
│   │   │   └── lidar_detector_node.py
│   │   ├── traffic_light_detector/
│   │   │   └── traffic_light_detector_node.py
│   │   └── perception_fusion/
│   │       └── perception_fusion_node.py  # Outputs PerceptionContext
│   ├── planning/
│   │   ├── behavior_planner/
│   │   │   └── behavior_planner_node.py
│   │   ├── trajectory_planner/
│   │   │   └── trajectory_planner_node.py # ACADOS Python interface
│   │   └── trajectory_selector/
│   │       └── trajectory_selector_node.py
│   ├── control/
│   │   └── controller/
│   │       └── controller_node.py         # 100Hz PID
│   ├── safety/
│   │   ├── aeb/
│   │   ├── fcw/
│   │   └── mrm/
│   ├── system/
│   │   ├── inference_daemon/
│   │   ├── camera_daemon/
│   │   ├── thermal_daemon/
│   │   ├── power_daemon/
│   │   └── health_daemon/
│   └── vehicle_bridge/
│       └── vehicle_bridge_node.py         # ROS2 bridge
├── third_party/
│   ├── rknpu2/
│   ├── hef_rt/
│   ├── rockchip_rga/
│   └── mpp/
├── models/
│   └── rk3688/
└── tools/
    └── systemd/
```

**No CMakeLists.txt. No package.xml. No C++ source files in `src/`.**
The entire application layer is Python. Third-party HAL libraries (rknpu2, etc.) remain as prebuilt binaries.

---

## Python Node Pattern (Dorapilot Standard)

All dorapilot nodes follow this pattern. No C++ nodes needed.

```python
#!/usr/bin/env python3
# src/perception/lidar_detector/lidar_detector_node.py
from dora import Node
import pyarrow as pa
import numpy as np

from drp_msgs import PointCloud2, DetectedObjectArray
from drp_msgs.utils import to_arrow, from_arrow

class LidarDetectorNode:
    def __init__(self):
        self.node = Node()
        self.model = self.load_rknn_model()

    def run(self):
        for event in self.node:
            if event["type"] == "INPUT":
                self.on_input(event)
            elif event["type"] == "STOP":
                break

    def on_input(self, event):
        # Receive PointCloud2 from DORA (zero-copy)
        pc2 = from_arrow(event["value"], PointCloud2)
        points = pc2.to_numpy()

        # Run NPU inference
        objects_3d = self.model.infer(points)

        # Send DetectedObjectArray back to DORA
        result = DetectedObjectArray(
            header=pc2.header,
            objects=objects_3d
        )
        self.node.send_output("objects_3d", to_arrow(result))

    def load_rknn_model(self):
        from rknnlite.api import RKNNLite
        rknn = RKNNLite()
        rknn.load_rknn("/data/models/pointpillars_rk3688.rknn")
        rknn.init_runtime(core_mask=RKNNLite.NPU_CORE_1)
        return rknn

if __name__ == "__main__":
    LidarDetectorNode().run()
```

### Operator Pattern (In-Process)

```python
#!/usr/bin/env python3
# src/sensing/operators/pointcloud_filter.py
from dora import DoraStatus
import numpy as np

from drp_msgs import PointCloud2
from drp_msgs.utils import to_arrow, from_arrow

class Operator:
    def on_event(self, dora_event, send_output):
        if dora_event["type"] == "INPUT":
            return self.on_input(dora_event, send_output)
        return DoraStatus.CONTINUE

    def on_input(self, dora_input, send_output):
        pc2 = from_arrow(dora_input["value"], PointCloud2)
        points = pc2.to_numpy()

        # Crop box filter (numpy-vectorized, C-speed)
        mask = ((points[:, 0] > -50) & (points[:, 0] < 50) &
                (points[:, 1] > -25) & (points[:, 1] < 25))
        filtered = points[mask]

        # Voxel grid downsample
        # ... (numpy operations) ...

        result = PointCloud2.from_xyz_array(filtered, header=pc2.header)
        send_output("points_filtered", to_arrow(result))
        return DoraStatus.CONTINUE
```

---

## Performance Budgets

| Stage | Rate | Latency Budget | DORA Overhead | Net Budget |
|-------|------|----------------|---------------|------------|
| Camera capture | 30Hz | 33ms | <0.1ms (SHM) | ~32ms for ISP + encode |
| Image preprocess | 30Hz | 33ms | <0.1ms (operator) | ~5ms (RGA crop/resize) |
| Driving vision (NPU) | 20Hz | 50ms | <0.1ms (SHM) | ~20ms (RKNN Core 0) |
| Driving policy (NPU) | 20Hz | 50ms | <0.1ms (SHM) | ~10ms (RKNN Core 0) |
| LiDAR perception (NPU) | 10Hz | 100ms | <0.1ms (SHM) | ~30ms (RKNN Core 1) |
| Perception fusion | 20Hz | 50ms | <0.1ms (SHM) | ~15ms (CPU, Python+numpy) |
| Behavior planning | 20Hz | 50ms | <0.1ms (SHM) | ~5ms (CPU, Python) |
| Trajectory MPC | 20Hz | 50ms | <0.1ms (SHM) | ~2ms (ACADOS) |
| Control (PID) | 100Hz | 10ms | <0.05ms (operator) | ~1ms (CPU) |

**Total pipeline latency (camera → vehicle command):**
- VisionPilot (ROS2): ~45ms + 15ms DDS overhead = **~60ms**
- DoraPilot (DORA): ~45ms + 0.5ms SHM overhead = **~46ms**
- **Gain: ~14ms (23% reduction)** — entirely from eliminated serialization

---

## Deployment Modes

### Development Mode

```bash
# Single-machine, no coordinator, console output
# Python nodes execute directly — no build step
dora run dataflows/dorapilot_main.yml --verbose
```

### Production Mode

```bash
# Start coordinator + daemon
dora up

# Start main pipeline
dora start dataflows/dorapilot_main.yml --name dorapilot_main --attach

# Start safety pipeline (separate for isolation)
dora start dataflows/dorapilot_safety.yml --name dorapilot_safety --attach

# Monitor
dora top
```

### Record/Replay Mode

```bash
# Record a drive
dora record dataflows/dorapilot_main.yml --output /data/records/drive_$(date +%s).drec

# Replay with experimental model
dora replay /data/records/drive_*.drec \
  --substitute driving_vision:experimental_model.py \
  --speed 1.0
```

---

## ACADOS MPC Integration (Python-Only)

VisionPilot's `trajectory_planner` uses ACADOS via Python interface. Preserved unchanged:

```python
from acados_template import AcadosOcpSolver
import numpy as np

class TrajectoryPlannerNode:
    def __init__(self):
        self.solver = AcadosOcpSolver(self.create_ocp())

    def plan(self, maneuver, context):
        x0 = np.array([context.position_x, context.position_y,
                       context.velocity_mps, context.heading_rad])
        self.solver.set(0, "lbx", x0)
        self.solver.set(0, "ubx", x0)
        status = self.solver.solve()
        trajectory = self.solver.get(1, "x")
        return trajectory
```

No C++ node needed. Generated C solver is a shared library loaded by Python.

---

## Hardware Platform Notes

### NPU Platform Comparison

DoraPilot supports two NPU families. Current production targets RK3688 (RKNN); Hailo is the planned upgrade path for ExoPilot 05+.

| Feature | RK3688 (current) | Hailo-10H | Hailo-15H (target) |
|---|---|---|---|
| AI TOPS | 12 | 10 | 20 |
| CPU cores | 4× A76 + 4× A55 | 2× A53 | 4× A53 |
| Camera interface | MIPI CSI-2 (via SoC) | MIPI CSI-2 (1–2 sensors) | MIPI CSI-2 (up to 4 sensors) |
| ISP | Rockchip ISP2 | Basic ISP | Advanced multi-sensor ISP |
| Video encode | H.265/H.264, 4K | H.265/H.264, 1080p | H.265/H.264, 4K |
| Model format | `.rknn` | `.hef` | `.hef` |
| Power envelope | Higher (full SoC) | Lower | Mid |
| Best fit | ExoPilot 03/04 | Single-camera IoT | Multi-camera ADAS |

### Hailo-15H: CSI Camera Pipeline

The Hailo-15H is a vision processor SoC — CSI cameras connect directly to it, not through a host CPU. The full pipeline runs on-chip:

```
MIPI CSI-2 camera(s) → ISP (demosaic, AWB, AE, NR) → Hailo AI Engine (20 TOPS) → H.265 encode / metadata output
```

**Key points for DoraPilot integration:**

- Supports up to **4 MIPI CSI-2 cameras** simultaneously with hardware frame sync
- RAW Bayer sensors processed by the on-chip ISP — no host ISP work needed
- Compatible sensors: Sony IMX series, OmniVision, etc. (standard MIPI CSI-2)
- Linux driver: V4L2 via Hailo Media Library SDK
- Output to host: PCIe or GbE, carrying structured inference metadata (not raw frames)
- Model format: `.hef` — same as Hailo-10H, compiled via Hailo Dataflow Compiler

**DORA node pattern for Hailo-15H** (replaces V4L2 `camera_node.py` + `driving_vision_node.py`):

```python
# src/sensing/hailo15h/hailo_vision_node.py
# CSI capture + ISP + inference all happen inside the 15H.
# This node receives structured output from the Hailo Media Library daemon.
from hailo_platform import HailoRTClient

class Hailo15HVisionNode:
    def __init__(self):
        self.node = Node()
        self.client = HailoRTClient("/dev/hailo0")  # PCIe device
        self.client.load_network_group("driving_vision.hef")

    def run(self):
        for event in self.node:
            if event["type"] == "INPUT" and event["id"] == "tick":
                result = self.client.infer()            # CSI→ISP→inference on-chip
                self.node.send_output("features", to_arrow(result.features))
                self.node.send_output("engagement", to_arrow(result.engagement))
```

**Dataflow change for Hailo-15H:** The separate `camera` and `driving_vision` nodes collapse into one `hailo_vision` node. The `image_preprocess` operator is also eliminated — the on-chip ISP handles it.

```yaml
# dataflows/dorapilot_main_hailo15h.yml (variant)
nodes:
  - id: hailo_vision              # replaces: camera + image_preprocess + driving_vision
    path: src/sensing/hailo15h/hailo_vision_node.py
    inputs:
      tick: dora/timer/millis/33
    outputs: [features, engagement]
    env:
      HAILO_DEVICE: /dev/hailo0
      MODEL_PATH: /data/models/driving_vision.hef
      CSI_CAMERAS: "0,1"          # use CSI port 0 (front) + port 1 (rear)
```

### Choosing Between Hailo-15H and Hailo-10H

- **Hailo-15H**: Use for multi-camera ADAS (front + side + rear), 4K capture, or when the full sensing→inference pipeline must run off-host. Recommended for ExoPilot 05+.
- **Hailo-10H**: Use for single-camera, cost/power-constrained designs where 10 TOPS is sufficient. Not a fit for multi-model parallel inference (driving_vision + lane_detector simultaneously).

---

## Next Steps

1. **Port inference HAL** from VisionPilot's `system/inference_ecu`
2. **Implement** camera capture node with V4L2 (RK3688 path)
3. **Implement** Pandar QT64 packet parser in `lidar_node.py`
4. **Port** VisionPilot's driving_vision + driving_policy RKNN inference
5. **Validate** camera → preprocess → driving_vision pipeline end-to-end
6. **Benchmark** latency vs VisionPilot on identical hardware
7. **Prototype** Hailo-15H `hailo_vision_node.py` with front CSI camera

---

*Architecture v2.0 — 2026-05-30 — Hybrid Autoware + VisionPilot Edition*
