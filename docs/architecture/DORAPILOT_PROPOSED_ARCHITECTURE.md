# DoraPilot Proposed Architecture v1.0 — Python-Native Stack

**Date:** 2026-05-30  
**Status:** Draft — Pending Review  
**Target:** ExoPilot 03 (RK3688), ExoPilot 04 (RKxxxx)  
**Middleware:** dora-rs 1.0 + ROS2 Humble (bridged at boundaries only)  
**Language:** Python 3.10+ for all application nodes (no C++ application code, no CMake)

---

## Why DORA for DoraPilot (Successor to VisionPilot)

VisionPilot proved that a Python-centric ADAS stack can work on edge SoC. DoraPilot replaces ROS2 with **dora-rs** to solve the one problem Python+ROS2 cannot fix: **inter-process communication overhead on large payloads**.

| Pain Point in VisionPilot (ROS2) | DORA Solution | Impact on Dorapilot |
|-----------------------------------|---------------|---------------------|
| PointCloud2 serialization eats 15–20% CPU core just moving data | Zenoh SHM zero-copy: pointer pass, not data copy | More TOPS for inference, not IPC |
| 150 packages, nested Python launch files, scattered param YAMLs | Single `dataflow.yml` declares entire pipeline | Onboard debugging in minutes, not hours |
| Static topology: A/B test requires full system restart | `dora node add/disconnect` at runtime | Parallel model evaluation without reboot |
| ROS2 bags: no node substitution for regression testing | `.drec` record/replay with `--substitute` | Same sensor inputs, different algorithms |
| `ros2 topic hz` + external Prometheus for observability | `dora top`, `dora trace view` built-in | Production observability out of the box |
| GIL contention + CDR deserialization in Python nodes | Apache Arrow format: zero deserialization overhead | Python nodes run at full speed |

**The LiDAR imperative:** Pandar QT64 produces ~200,000 points/frame ≈ 2–3 MB at 10 Hz. In ROS2, this payload balloons latency to 5–15 ms with jitter. In DORA, it is a **shared memory pointer pass** — <1 ms, flat. This is not incremental; it is transformative for real-time fusion.

---

## What Changes from VisionPilot

### Architecture Changes

| Aspect | VisionPilot (ROS2) | DoraPilot (DORA) |
|--------|-------------------|------------------|
| **Pipeline definition** | 150 packages + nested Python launch files | Single `dataflow.yml` per pipeline |
| **IPC mechanism** | DDS CDR serialization | Zenoh SHM zero-copy (Apache Arrow) |
| **Node language** | Python 3.10 + C++ wrappers (mixed) | **Python 3.10+ only** — no C++ application code |
| **Build system** | colcon + CMake + package.xml | `pip install dora-rs` + `dora run dataflow.yml` |
| **Perception fusion data** | ROS2 PointCloud2 msg (serialized) | PyArrow arrays + numpy views (zero-copy) |
| **Control loop (100Hz)** | ROS2 node with DDS overhead | DORA operator in-process (<100 µs overhead) |
| **Safety restart** | External systemd watchdog | Native `restart_policy: on_failure` |
| **Record/replay** | MCAP bag (no substitution) | `.drec` with `--substitute` for regression testing |
| **A/B testing** | Full system restart required | `dora node add` at runtime |
| **Observability** | External tooling required | `dora top`, `dora trace` built-in |

### What Stays the Same

- **3-layer boundary** (Application / System / Third_Party) — preserved
- **Functional naming** (`npu_rockchip`, `dmu_rga`) — preserved
- **Daemon pattern** (`camera_daemon`, `thermal_daemon`) — preserved as DORA nodes
- **MPC + PID two-layer control** (20Hz + 100Hz) — preserved
- **Budget-based NPU allocation** (85% TOPS safety line) — preserved
- **Unit suffixes** (`_mps`, `_deg`, `_rad`) — preserved in data dictionaries
- **ACADOS solver** — stays Python interface (`gen_long_mpc.py` + generated C solver binary). No C++ node needed.
- **RKNN/Hailo NPU models** — same `.rknn`/`.hef` files, same inference daemon pattern

---

## Best Practices from dora-autoware (Ported Experience)

The **dora-autoware** project (github.com/dora-rs/dora-autoware) ported Autoware.universe to DORA and demonstrated real-vehicle deployment at GOSIM 2024. Key lessons for dorapilot:

### 1. Keep LiDAR Pipeline 100% DORA-Native
The dora-autoware team hit a **blocker** with the ROS2 bridge: PointCloud2 struct arrays panic the Arrow↔ROS2 converter (`"Struct array's data type is not struct!"`). Their fix: **never bridge PointCloud2**. Dorapilot follows this rule strictly.

### 2. Parse Raw Bytes in Python (No C++ Parser Needed)
Autoware's NDT localization was ported to DORA using the **Python API** with numpy byte parsing:
```python
# Direct byte layout parsing — same performance as C++ for this workload
import numpy as np
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
4. **Operators for lightweight transforms, Nodes for heavy compute** — minimize process overhead where safe
5. **Safety-critical isolation** — AEB/FCW/MRM run as dedicated nodes with `restart_policy: never`
6. **Declarative everything** — `dataflow.yml` defines the pipeline, not Python launch files
7. **No serialization tax on LiDAR** — PointCloud2 stays in DORA-native Arrow format; never bridges to ROS2

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DoraPilot v1.0 — Complete Stack                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    DORA DATAFLOW (Zero-Copy SHM)                     │   │
│  │                                                                      │   │
│  │  SENSING              PERCEPTION           PLANNING        CONTROL   │   │
│  │  ────────             ──────────           ────────        ───────   │   │
│  │  camera_node    ──► driving_vision  ──► behavior_planner ──►       │   │
│  │       │                │                     │              controller│   │
│  │       │                │                     │                 │     │   │
│  │  lidar_node ─────► lidar_perception ──► trajectory_planner ──►     │   │
│  │       │                │                     │                 │     │   │
│  │       │                ▼                     ▼                 ▼     │   │
│  │       └──► perception_fusion ─────────────► trajectory_selector     │   │
│  │                                                                      │   │
│  │  OPERATORS (in-process): crop_resize, voxel_filter, pid_control     │   │
│  │                                                                      │   │
│  └──────────────────────────────┬──────────────────────────────────────┘   │
│                                 │                                           │
│                                 ▼ ROS2 Bridge                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    ROS2 ECOSYSTEM (Boundary Layer)                   │   │
│  │                                                                      │   │
│  │  Vehicle Interface    CAN Driver    Dashboard    Voice    Navigation │   │
│  │  ─────────────────    ─────────    ──────────    ─────    ────────── │   │
│  │  vehicle_interface ──► can_driver    ui_node     whisper   valhalla  │   │
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

## Dataflow Definition

### Main Pipeline (`dataflows/dorapilot_main.yml`)

```yaml
# DoraPilot Main Dataflow — RK3688 Configuration
# camera (30Hz) → preprocess → perception (20Hz) → planning (20Hz) → control (100Hz)
# ALL nodes are Python scripts. No C++ nodes, no CMake.

nodes:
  # ─── SENSING ───
  - id: camera
    path: src/sensing/camera_node/camera_node.py
    inputs:
      tick: dora/timer/millis/33          # ~30Hz
    outputs:
      - image_raw
    env:
      CAMERA_DEVICE: /dev/video0
      WIDTH: 1920
      HEIGHT: 1080
      FORMAT: nv12

  - id: lidar
    path: src/sensing/lidar_node/lidar_node.py
    inputs:
      tick: dora/timer/millis/100         # 10Hz
    outputs:
      - pointcloud
    env:
      LIDAR_MODEL: pandar_qt64
      LIDAR_IP: 192.168.1.201

  - id: gnss
    path: src/sensing/gnss_node/gnss_node.py
    outputs:
      - fix

  - id: imu
    path: src/sensing/imu_node/imu_node.py
    outputs:
      - raw

  # ─── PREPROCESSING (Operators for zero-overhead transforms) ───
  - id: image_preprocess
    operators:
      python: src/sensing/operators/image_preprocess.py
    inputs:
      image_raw: camera/image_raw
    outputs:
      - image_resized
      - image_yuv
    env:
      RESIZE_WIDTH: 512
      RESIZE_HEIGHT: 256
      # Use RGA hardware accel if available
      USE_RGA: "true"

  - id: pointcloud_filter
    operators:
      python: src/sensing/operators/pointcloud_filter.py
    inputs:
      pointcloud: lidar/pointcloud
    outputs:
      - points_filtered
    env:
      VOXEL_SIZE: 0.1
      CROP_BOX_MIN: "[-50, -25, -3]"
      CROP_BOX_MAX: "[50, 25, 1]"

  # ─── NPU PERCEPTION (Isolated nodes for crash safety) ───
  - id: driving_vision
    path: src/perception/driving_vision_node/driving_vision_node.py
    inputs:
      image: image_preprocess/image_yuv
    outputs:
      - features          # 1024-dim feature vector
      - engagement
    env:
      MODEL_PATH: /data/models/driving_vision_rk3688.rknn
      NPU_CORE: "0"
    restart_policy: on_failure
    max_restarts: 3

  - id: driving_policy
    path: src/perception/driving_policy_node/driving_policy_node.py
    inputs:
      features: driving_vision/features
      vehicle_state: vehicle_bridge/vehicle_state
    outputs:
      - neural_path
      - leads
    env:
      MODEL_PATH: /data/models/driving_policy_rk3688.rknn
      NPU_CORE: "0"
    restart_policy: on_failure
    max_restarts: 3

  - id: lane_detection
    path: src/perception/lane_detection_node/lane_detection_node.py
    inputs:
      image: image_preprocess/image_resized
    outputs:
      - lane_lines
    env:
      MODEL_PATH: /data/models/lane_detector_rk3688.rknn
      NPU_CORE: "1"

  - id: lidar_perception
    path: src/perception/lidar_perception_node/lidar_perception_node.py
    inputs:
      pointcloud: pointcloud_filter/points_filtered
    outputs:
      - objects_3d
    env:
      MODEL_PATH: /data/models/pointpillars_rk3688.rknn
      NPU_CORE: "1"

  # ─── SAFETY PERCEPTION (Lower rate, CPU-based) ───
  - id: safety_perception
    path: src/perception/safety_perception_node/safety_perception_node.py
    inputs:
      image: image_preprocess/image_resized
      objects_3d: lidar_perception/objects_3d
    outputs:
      - safety_events
    env:
      DETECTORS: "stop_line,pedestrian,cyclist,road_condition,school_zone,work_zone"
    restart_policy: never                         # Safety-critical: manual restart only

  # ─── PERCEPTION FUSION ───
  - id: perception_fusion
    path: src/perception/perception_fusion_node/perception_fusion_node.py
    inputs:
      neural_path: driving_policy/neural_path
      leads: driving_policy/leads
      lane_lines: lane_detection/lane_lines
      objects_3d: lidar_perception/objects_3d
      safety_events: safety_perception/safety_events
      gnss_fix: gnss/fix
      imu_raw: imu/raw
    outputs:
      - perception_context
    env:
      FUSION_RATE: "20"

  # ─── BEHAVIOR PLANNING ───
  - id: behavior_planner
    path: src/planning/behavior_planner_node/behavior_planner_node.py
    inputs:
      context: perception_fusion/perception_context
    outputs:
      - maneuver_command
    env:
      PLANNING_RATE: "20"

  # ─── TRAJECTORY PLANNING (MPC via Python ACADOS interface) ───
  - id: trajectory_planner
    path: src/planning/trajectory_planner_node/trajectory_planner_node.py
    inputs:
      maneuver: behavior_planner/maneuver_command
      context: perception_fusion/perception_context
    outputs:
      - trajectory
    env:
      MPC_HORIZON: "20"
      MPC_DT: "0.05"
      SOLVER: acados
    cpu_affinity: [4, 5]                          # Isolate MPC cores

  # ─── TRAJECTORY SELECTOR (Parallel generators) ───
  - id: trajectory_selector
    path: src/planning/trajectory_selector_node/trajectory_selector_node.py
    inputs:
      neural_trajectory: trajectory_planner/trajectory
      classical_trajectory: auto_speed/classical_path
    outputs:
      - selected_trajectory
    env:
      SELECTOR_MODE: safety_first                 # safety_gate → voting → arbitration

  # ─── CONTROL (100Hz, operators for speed) ───
  - id: controller
    path: src/control/controller_node/controller_node.py
    inputs:
      trajectory: trajectory_selector/selected_trajectory
      vehicle_state: vehicle_bridge/vehicle_state
    outputs:
      - lateral_cmd
      - longitudinal_cmd
    env:
      CONTROL_RATE: "100"
      LATERAL_MODE: torque_pid
      LONGITUDINAL_MODE: openpid
    cpu_affinity: [6, 7]                          # Isolate control cores
    restart_policy: never                         # Safety-critical

  # ─── ROS2 BRIDGE (Vehicle boundary — simple structs only) ───
  - id: vehicle_bridge
    path: dora-ros2-bridge
    inputs:
      lateral_cmd: controller/lateral_cmd
      longitudinal_cmd: controller/longitudinal_cmd
    outputs:
      - vehicle_state
    env:
      ROS2_TOPIC_MAPPING: |
        lateral_cmd -> /control/lateral_cmd
        longitudinal_cmd -> /control/longitudinal_cmd
        vehicle_state <- /vehicle/status
      ROS2_DOMAIN_ID: "0"
```

### Safety Dataflow (`dataflows/dorapilot_safety.yml`)

Safety-critical nodes run in a **separate dataflow** for isolation:

```yaml
# Independent safety dataflow — can survive main dataflow restart
# ALL nodes are Python. No C++ application code.
nodes:
  - id: aeb
    path: src/safety/aeb_node/aeb_node.py
    inputs:
      context: main/perception_context          # subscribe to main dataflow
      vehicle_state: vehicle_bridge/vehicle_state
    outputs:
      - emergency_brake_request
    restart_policy: never
    input_timeout:
      context: 100ms                            # circuit breaker

  - id: fcw
    path: src/safety/fcw_node/fcw_node.py
    inputs:
      context: main/perception_context
    outputs:
      - forward_collision_warning
    restart_policy: never

  - id: mrm_handler
    path: src/safety/mrm_handler_node/mrm_handler_node.py
    inputs:
      emergency_brake: aeb/emergency_brake_request
      fcw: fcw/forward_collision_warning
      system_health: health_daemon/status
    outputs:
      - mrm_command
    restart_policy: never
```

---

## Python Node Pattern (Dorapilot Standard)

All dorapilot nodes follow this pattern. No C++ nodes needed.

```python
# src/perception/lidar_perception_node/lidar_perception_node.py
from dora import Node
import pyarrow as pa
import numpy as np
import json

class LidarPerceptionNode:
    def __init__(self):
        self.node = Node()
        # Load RKNN model via inference_daemon or direct NPU API
        self.model = self.load_model()

    def run(self):
        for event in self.node:
            if event["type"] == "INPUT":
                self.on_input(event)
            elif event["type"] == "STOP":
                break

    def on_input(self, event):
        # Zero-copy: event["value"] is a PyArrow array
        # Convert to numpy view for processing
        data = event["value"].to_numpy().view(np.uint8)
        
        # Parse pointcloud from raw bytes (same layout as ROS2 PointCloud2)
        points = np.frombuffer(data, dtype=np.float32).reshape(-1, 4)
        
        # Run NPU inference
        objects_3d = self.model.infer(points)
        
        # Send output as JSON-serialized Arrow array
        result_json = json.dumps(objects_3d)
        self.node.send_output("objects_3d", pa.array([result_json]))

    def load_model(self):
        from rknnlite.api import RKNNLite
        rknn = RKNNLite()
        rknn.load_rknn("/data/models/pointpillars_rk3688.rknn")
        rknn.init_runtime(core_mask=RKNNLite.NPU_CORE_1)
        return rknn

if __name__ == "__main__":
    node = LidarPerceptionNode()
    node.run()
```

### Operator Pattern (In-Process)

```python
# src/sensing/operators/pointcloud_filter.py
import pyarrow as pa
import numpy as np

class PointcloudFilter:
    def __init__(self):
        self.voxel_size = 0.1
        self.crop_min = np.array([-50, -25, -3])
        self.crop_max = np.array([50, 25, 1])

    def on_input(self, dora_input, send_output):
        data = dora_input["value"].to_numpy().view(np.uint8)
        points = np.frombuffer(data, dtype=np.float32).reshape(-1, 4)
        
        # Crop box filter (numpy-vectorized, C-speed)
        mask = np.all((points[:, :3] >= self.crop_min) & (points[:, :3] <= self.crop_max), axis=1)
        filtered = points[mask]
        
        # Voxel grid downsample (simple)
        voxel_indices = np.floor(filtered[:, :3] / self.voxel_size).astype(np.int32)
        _, unique_indices = np.unique(voxel_indices, axis=0, return_index=True)
        downsampled = filtered[unique_indices]
        
        send_output("points_filtered", pa.array(downsampled.tobytes()))
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
│   ├── dorapilot_voice.yml                # Voice assistant (optional)
│   └── modules/
│       └── navigation.module.yml          # Reusable nav sub-graph
├── docs/
│   ├── research/
│   │   ├── DORA_MIGRATION_RESEARCH.md     # Full research doc
│   │   └── DORA_PROS_CONS.md              # Comparative analysis
│   └── architecture/
│       └── DORAPILOT_PROPOSED_ARCHITECTURE.md  # This file
├── src/                                   # ALL Python application code
│   ├── sensing/
│   │   ├── camera_node/
│   │   │   └── camera_node.py
│   │   ├── lidar_node/
│   │   │   └── lidar_node.py
│   │   ├── gnss_node/
│   │   ├── imu_node/
│   │   └── operators/
│   │       ├── image_preprocess.py
│   │       └── pointcloud_filter.py
│   ├── perception/
│   │   ├── driving_vision_node/
│   │   │   └── driving_vision_node.py
│   │   ├── driving_policy_node/
│   │   ├── lane_detection_node/
│   │   ├── lidar_perception_node/
│   │   ├── safety_perception_node/
│   │   └── perception_fusion_node/
│   ├── planning/
│   │   ├── behavior_planner_node/
│   │   ├── trajectory_planner_node/       # Python + ACADOS Python interface
│   │   └── trajectory_selector_node/
│   ├── control/
│   │   ├── controller_node/
│   │   └── operators/
│   │       ├── lateral_pid.py
│   │       └── longitudinal_pid.py
│   ├── safety/
│   │   ├── aeb_node/
│   │   ├── fcw_node/
│   │   ├── bsd_node/
│   │   └── mrm_handler_node/
│   ├── system/
│   │   ├── inference_daemon/              # NPU/GPU/RGA/MPP HAL
│   │   ├── camera_daemon/
│   │   ├── thermal_daemon/
│   │   ├── power_daemon/
│   │   └── health_daemon/
│   └── vehicle_bridge/                    # ROS2 bridge config
├── third_party/
│   ├── rknpu2/                            # Rockchip NPU runtime
│   ├── hef_rt/                            # Hailo runtime
│   ├── rockchip_rga/                      # RGA 2D accelerator
│   └── mpp/                               # MPP video codec
├── models/
│   └── rk3688/                            # NPU model files (.rknn)
└── tools/
    ├── systemd/                           # Service templates
    └── switch.sh                          # System switching script
```

**No CMakeLists.txt. No package.xml. No C++ source files in `src/`.**
The entire application layer is Python. Third-party HAL libraries (rknpu2, etc.) remain as prebuilt binaries.

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
| Trajectory MPC | 20Hz | 50ms | <0.1ms (SHM) | ~2ms (ACADOS Python interface) |
| Control (PID) | 100Hz | 10ms | <0.05ms (operator) | ~1ms (CPU, Python) |

**Total pipeline latency (camera → vehicle command):**
- VisionPilot (ROS2): ~45ms + 15ms DDS overhead = **~60ms**
- DoraPilot (DORA): ~45ms + 0.5ms SHM overhead = **~46ms**
- **Gain: ~14ms (23% reduction)** — entirely from eliminated serialization

**Python performance note:** Numpy-vectorized operations (pointcloud filtering, matrix math) run at C speed. The Python GIL is not a bottleneck for these workloads. NPU inference uses RKNNLite Python API (C extension). ACADOS uses generated C solver called from Python. All heavy math is C underneath; Python orchestrates.

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

VisionPilot's `trajectory_planner` uses ACADOS via Python interface (`gen_long_mpc.py`). This pattern is preserved unchanged in dorapilot:

```python
# src/planning/trajectory_planner_node/trajectory_planner_node.py
from acados_template import AcadosOcpSolver
import numpy as np

class TrajectoryPlannerNode:
    def __init__(self):
        self.solver = AcadosOcpSolver(self.create_ocp())
        
    def plan(self, maneuver, context):
        # Set initial state from perception context
        x0 = np.array([context.position_x, context.position_y, 
                       context.velocity_mps, context.heading_rad])
        self.solver.set(0, "lbx", x0)
        self.solver.set(0, "ubx", x0)
        
        # Solve MPC (generated C solver, Python interface)
        status = self.solver.solve()
        trajectory = self.solver.get(1, "x")
        return trajectory
```

No C++ node needed. The generated C solver is a shared library loaded by Python. This is the standard ACADOS workflow.

---

## Next Steps

1. **Review** this architecture with the team
2. **Bootstrap** DORA on RK3688 dev board: `pip install dora-rs`, verify `dora run` works
3. **Port** `inference_daemon` from VisionPilot's `system/inference_ecu` (Python layer unchanged)
4. **Validate** camera → preprocess → driving_vision pipeline end-to-end
5. **Benchmark** latency vs VisionPilot on identical hardware
6. **Iterate** on dataflow YAML based on real-world timing

---

*Architecture draft v1.0 — 2026-05-30 — Python-Native Edition*
