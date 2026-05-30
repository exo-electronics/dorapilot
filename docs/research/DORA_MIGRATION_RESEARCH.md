# DORA Migration Research: From VisionPilot (ROS2) to DoraPilot — Python-Native

**Date:** 2026-05-30  
**Status:** Research Complete — Architecture Proposal Ready  
**Target:** ExoPilot 03+ (RK3688, LiDAR-enabled, 12 TOPS NPU)  
**Language Stance:** Python 3.10+ for all application nodes. No C++ nodes, no CMake, no package.xml for DORA-native components.

> 📋 **Companion Document:** See [`DORA_PROS_CONS.md`](./DORA_PROS_CONS.md) for detailed comparative analysis, benchmark data, and risk assessment.

---

## Executive Summary

DoraPilot is the next-generation ADAS stack replacing VisionPilot's ROS2-centric architecture with **dora-rs** (Dataflow-Oriented Robotic Architecture). DORA provides **10-31× faster IPC** than ROS2 (validated by arxiv peer-reviewed benchmarks), zero-copy shared memory via Zenoh/Apache Arrow, declarative dataflow pipelines, and native record/replay — critical advantages for real-time LiDAR+camera fusion at 20Hz on resource-constrained edge SoCs.

**Key validation:** The Feb 2026 arxiv paper *"DORA: Dataflow Oriented Robotic Architecture"* (2602.13252v1) rigorously benchmarks DORA against ROS2 Humble/FastDDS and CyberRT. For 4MB payloads at 20Hz (typical for camera+LiDAR), DORA achieves **0.82 ms** latency vs ROS2's **17.1 ms** — a **21× advantage**. For 32MB LiDAR bursts, DORA is **31× faster** (2.78 ms vs 87 ms). Real-world robot arm deployment showed DORA at **1.5 ms** vs ROS2 at **22 ms**.

**Python-native commitment:** All application nodes in dorapilot are Python. DORA's Python API (`pip install dora-rs`, `from dora import Node`) is first-class and production-ready. There are no C++ application nodes, no CMake build steps, and no Rust required for daily development. The Rust core handles IPC; Python handles ADAS logic.

Additionally, the **dora-autoware** project has already demonstrated porting Autoware modules to DORA using the Python API, and GOSIM China 2024 featured a presentation on *"The Application of Dora in the Autonomous Driving"* reporting real-vehicle implementation.

| Dimension | VisionPilot (ROS2) | DoraPilot (DORA) |
|-----------|-------------------|------------------|
| **IPC Latency (4MB @ 20Hz)** | 17.1 ms (FastDDS) | **0.82 ms** (Zenoh SHM) |
| **IPC Latency (32MB @ 50Hz)** | 87 ms | **2.78 ms** |
| **Multi-destination (1→4)** | 15.3 ms | **<1 ms** |
| **CPU Overhead (deserialization)** | >30% | **~0%** |
| **Payload Scaling** | Latency spikes with PointCloud2 (MB-scale) | Flat latency 4KB→4MB |
| **Pipeline Definition** | Python launch files + param YAML | Declarative `dataflow.yml` |
| **Language** | Python 3.10 + C++ (mixed, wrappers) | **Python 3.10+ only** |
| **Build System** | colcon + CMake + package.xml | `pip install dora-rs` — no build for app code |
| **Hot Reload** | Restart entire launch | Python operator hot-reload |
| **Record/Replay** | MCAP bag (ROS2 native) | `.drec` native + node substitution |
| **Dynamic Topology** | Static at launch | `dora node add/remove/connect` live |
| **Observability** | `ros2 topic hz/echo` | `dora top`, `dora topic hz`, built-in tracing |
| **Distributed** | ROS2 multicast (complex) | Zenoh auto-fallback, SSH cluster mgmt |

---

## Why DORA (The Migration Driver)

VisionPilot works. It runs on RK3588. It drives the car. So why migrate?

**Because ROS2's DDS serialization is a tax we can no longer afford once LiDAR joins the pipeline.**

| VisionPilot Scenario | ROS2 Cost | DORA Benefit |
|---------------------|-----------|--------------|
| LiDAR pointcloud (2.4MB) moves from lidar_node → perception_fusion | 5–15ms jittery latency, 15–20% CPU core on serialization | <1ms flat, **0% CPU** on IPC |
| Camera image (1.5MB) moves from camera_node → driving_vision | 3–8ms latency, CDR copy | <0.5ms, pointer pass |
| A/B test classical vs neural planner | Full system restart | `dora node add` at runtime |
| Regression test new driving model | Re-record bag, manual remapping | `dora replay --substitute` |
| Debug on vehicle | Navigate 150 packages, nested launch files | Single `dataflow.yml` + `dora top` |

**DORA replaces ROS2, not Python.** VisionPilot's Python code — NPU inference, MPC planning, PID control — stays Python. Only the middleware changes.

---

## What Changes from VisionPilot

### What Changes

1. **Middleware:** ROS2 DDS → DORA Zenoh SHM (zero-copy)
2. **Pipeline config:** 150 packages + launch files → single `dataflow.yml`
3. **Build system:** colcon + CMake → `pip install dora-rs` (no build for app code)
4. **Message format:** ROS2 `.msg` IDL → Apache Arrow arrays + Python dicts
5. **Node packaging:** One node per package → operators co-located, nodes as Python scripts
6. **Record/replay:** MCAP bag → `.drec` with node substitution
7. **Observability:** External Grafana → `dora top` built-in
8. **Topology:** Static at launch → dynamic runtime changes

### What Does NOT Change

1. **Python application code** — all inference, planning, control stays Python
2. **ACADOS MPC** — same Python interface (`gen_long_mpc.py`), same generated C solver library
3. **RKNN/Hailo models** — same `.rknn`/`.hef` files, same inference daemon pattern
4. **3-layer boundary** (App / System / Third_Party) — preserved
5. **Daemon pattern** — `camera_daemon`, `thermal_daemon` preserved as DORA nodes
6. **MPC + PID control layers** (20Hz + 100Hz) — preserved
7. **NPU budget allocation** (85% TOPS safety line) — preserved
8. **Vehicle CAN interface** — stays ROS2, bridged at boundary

---

## 1. VisionPilot Architecture Analysis

### 1.1 Current Stack (ROS2 Humble)

VisionPilot v2.0 runs **~150 packages** across 20+ categories:

```
src/
├── sensing/          (9 pkgs)   camera, lidar, imu, gnss, stereo
├── perception/       (27 pkgs)  driving_model, lane_detector, lidar_detector,
│                               traffic_light, object_tracker, fusion, ...
├── planning/         (19 pkgs)  behavior_planner, trajectory_planner,
│                               longitudinal/lateral_planner, MPC, ...
├── control/          (11 pkgs)  vehicle_controller, trajectory_follower,
│                               cmd_gate, joy_controller, ...
├── safety/           (5 pkgs)   aeb, fcw, bsd, lane_departure, mrm_handler
├── system/           (10 pkgs)  inference_ecu, camera_daemon, thermal,
│                               health_monitor, power_manager, ...
├── inference/        (6 pkgs)   model_host, preprocessor, rknn/hef/onnx backends
├── localization/     (7 pkgs)   ekf, ndt, gnss, yabloc, point_cloud
├── navigation/       (6 pkgs)   valhalla bridge, map_speed, poi, search
├── vehicle/          (5 pkgs)   can_codec, dbc_parser, torque_estimator
├── voice/            (11 pkgs)  wake_word, whisper_stt, nlu, tts, aec
├── actuator/         (7 pkgs)   vehicle_interface, can_driver, climate
├── dashboard/        (3 pkgs)   ui, calib, onboarding
├── common/           (shared libs)
└── evp_msgs/         (custom ROS message definitions)
```

### 1.2 Layer Boundaries (Well-Defined)

VisionPilot has excellent layer separation (from `docs/architecture/layer-boundaries.md`):

```
L3 APPLICATION  ──► sensing, perception, planning, control
       │            (ROS topics/services ONLY; NO direct hardware imports)
       ▼ ROS msgs
L2 SYSTEM      ──► camera_daemon, inference_ecu, thermal_daemon, power_daemon
       │            (HAL + BSP; ROS services expose hardware)
       ▼ direct calls
L1 THIRD_PARTY ──► rknpu2, hef_rt, rockchip_rga, mpp, arm_compute
       │            (ONLY accessed by system/inference_ecu/backends/)
       ▼
   HARDWARE
```

**This boundary discipline MUST be preserved** in DoraPilot. DORA's dataflow replaces L3↔L2 ROS topics, but the HAL/BSP abstraction stays.

### 1.3 Timing Architecture

| Stage | Rate | Technology |
|-------|------|------------|
| Sensing (cameras) | 30Hz | V4L2 → camera_daemon |
| NPU Perception | 20Hz | RKNN on NPU Core 0/1 |
| Safety Perception | 5-10Hz | CPU (pedestrian, cyclist, stop_line) |
| Perception Fusion | 20Hz | CPU — unified PerceptionContext |
| Behavior Planning | 20Hz | CPU — maneuver decisions |
| Trajectory Planning | 20Hz | ACADOS MPC (~1-2ms solve) |
| Control | 100Hz | Torque PID + OpenPID tracking |
| Actuation | 100Hz | CAN frames → Vehicle |

### 1.4 Pain Points in ROS2 (Why Migrate) — Benchmark-Validated

1. **Serialization overhead on large payloads**: LiDAR PointCloud2 messages (MB-scale) serialize/deserialize through DDS every hop. arxiv 2602.13252v1 shows ROS2 latency rises **610×** when payload grows from 32KB to 4MB over LAN. DORA's growth is only **36×**.
2. **Static topology**: Cannot A/B test two driving models without restarting the entire system.
3. **Launch complexity**: 150 packages orchestrated via nested Python launch files; parameter YAMLs scattered.
4. **ROS2 Python GIL contention + CPU waste**: Perception nodes spend >30% CPU on deserialization (arxiv paper). DORA's Apache Arrow format achieves **~0% deserialization overhead**.
5. **Distributed debug difficulty**: Multi-machine ROS2 requires DDS discovery tuning, multicast, domain IDs. DORA uses Zenoh with automatic cross-machine fallback.
6. **Record/replay size**: MCAP bags of LiDAR data are enormous; no built-in node substitution for regression testing.
7. **Message drops at high bandwidth**: dora-benchmark shows ROS2 C++ and ROS2 Python both **fail to sustain 20Hz at 40MB** (message drops). DORA Rust handles 40MB at 2523 µs (2.5 ms) consistently.

---

## 2. DORA in Autonomous Driving — Real-World Validation

Before committing to DORA, we investigated whether it has been used for real ADAS/AV stacks:

### 2.1 dora-autoware — Directly Relevant Precedent

The **dora-autoware** project (github.com/dora-rs/dora-autoware) is actively porting Autoware.universe modules to DORA. Key achievements:
- NDT localization module ported to DORA **Python API**
- Object detection and tracking in Python nodes
- Real-vehicle deployment demonstrated at **GOSIM China 2024** (Oct 2024)
- Presentation title: *"The Application of Dora in the Autonomous Driving"*
- **Critical lesson**: LiDAR PointCloud2 must stay DORA-native. The ROS2 bridge panics on struct arrays.

This proves DORA can handle the full AV pipeline: sensing → perception → localization → planning → control — **all from Python**.

### 2.2 dora-drives — Learning Platform

**dora-drives** provides a complete CARLA-simulated autonomous vehicle pipeline using DORA dataflows. It includes:
- Camera → object detection → planning → control loop
- YOLO integration
- End-to-end YAML-defined pipeline

This serves as a **reference architecture** for dorapilot's dataflow design.

### 2.3 Academic Benchmarking

The **Text2Scenario** paper (arxiv 2503.02911v1, Mar 2025) benchmarked Dora-RS alongside Apollo, Autoware, and Interfuser across 368 Carla scenarios. While Dora-RS scored poorly on collision avoidance (vision-only, no LiDAR), the fact it was included as a peer SUT validates DORA as a legitimate AV framework.

**Lesson for dorapilot:** DORA's communication framework is excellent, but perception quality depends on our models. We will use LiDAR + camera fusion (unlike dora-drives' vision-only approach).

---

## 3. DORA Architecture Deep-Dive

### 3.1 Core Concepts

DORA replaces "nodes + topics" with **dataflows**: directed graphs of nodes/operators connected by typed inputs/outputs.

```yaml
# dataflow.yml — declarative pipeline
# ALL nodes are Python scripts. No C++ nodes.
nodes:
  - id: camera
    path: src/sensing/camera_node/camera_node.py
    inputs:
      tick: dora/timer/millis/33    # ~30Hz
    outputs:
      - image

  - id: driving_vision
    path: src/perception/driving_vision_node/driving_vision_node.py
    inputs:
      image: camera/image
    outputs:
      - features                    # 1024-dim feature vector
      - engagement

  - id: driving_policy
    path: src/perception/driving_policy_node/driving_policy_node.py
    inputs:
      features: driving_vision/features
      vehicle_state: vehicle_bridge/vehicle_state
    outputs:
      - neural_path
      - leads

  - id: trajectory_selector
    path: src/planning/trajectory_selector_node/trajectory_selector_node.py
    inputs:
      neural_path: driving_policy/neural_path
      classical_path: auto_speed/path
      lidar_objects: lidar_detector/objects
    outputs:
      - selected_trajectory
```

### 3.2 Communication Layers

```
┌─────────────────────────────────────────────────────────────┐
│  CLI <-> Coordinator   (WebSocket :6013)                    │
│  Coordinator <-> Daemon (WebSocket)                         │
│  Daemon <-> Daemon      (Zenoh — cross-machine)             │
│  Node <-> Node          (Zenoh SHM — zero-copy >4KB)        │
│  Daemon <-> Node        (SHM / TCP — control + small msgs)  │
└─────────────────────────────────────────────────────────────┘
```

**Key for ADAS**: Zenoh SHM means a 1MB PointCloud2 from LiDAR daemon to perception fusion incurs **zero copy** — the pointer is passed, not the data.

### 3.3 Operators vs Nodes

| | Nodes | Operators |
|--|-------|-----------|
| **Process** | Standalone process | In-process (shared runtime) |
| **Overhead** | Higher (IPC) | Lower (function call) |
| **Use Case** | Heavy compute, crashes isolated | Lightweight transforms, preprocessing |
| **Language** | Python (our choice) | Python |
| **Example** | driving_vision NPU inference | resize, crop, format_convert, voxel_filter |

**Recommendation**: Use **operators** for image preprocessing (RGA-style crop/resize), coordinate transforms, and message filtering. Use **nodes** for NPU inference, MPC solver, and safety-critical modules (isolation).

### 3.4 ROS2 Bridge

DORA has a **bidirectional ROS2 bridge** (experimental, Foxy+):

```yaml
nodes:
  - id: ros2_bridge
    path: dora-ros2-bridge
    inputs:
      trajectory: trajectory_selector/selected_trajectory
    outputs:
      - vehicle_cmd                 # publishes to ROS2 /actuator/vehicle/command
    env:
      ROS2_TOPIC_MAPPING: |
        trajectory -> /planning/trajectory_selector/trajectory
```

This allows **gradual migration**: keep vehicle interface, CAN stack, and existing C++ Autoware controllers in ROS2 while moving perception/planning to DORA.

**⚠️ Known Limitation**: The ROS2 bridge has documented issues with complex nested structs like **PointCloud2** (github.com/dora-rs/dora-autoware/discussions/10). For dorapilot:
- **DO NOT** bridge LiDAR pointclouds through ROS2
- Keep LiDAR pipeline 100% DORA-native
- Bridge only simple structs at vehicle boundary (Twist, VehicleCommand)

---

## 4. Proposed DoraPilot Restructuring

### 4.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DoraPilot Stack v1.0 (DORA-native, Python-only)      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  L0: SENSING DAEMONS (DORA nodes, Python, various Hz)                       │
│  ├── camera       → camera/image           (Zenoh SHM)                     │
│  ├── lidar        → lidar/points           (Zenoh SHM, zero-copy)          │
│  ├── gnss         → gnss/fix                                               │
│  └── imu          → imu/raw                                                │
│                              ↓                                              │
│  L0.5: PREPROCESSING (DORA operators — in-process, ultra-low latency)       │
│  ├── crop_resize  → camera/image_resized   (operator: RGA-style)           │
│  ├── format_conv  → camera/image_yuv                                     │
│  └── pointcloud_filter → lidar/points_filtered                             │
│                              ↓                                              │
│  L1: NPU PERCEPTION (DORA nodes, Python, 20Hz)                              │
│  ┌─────────────┬─────────────┬─────────────────────────────────────────┐   │
│  │Core 0:      │Core 1:      │Core 2 (RK3688):                       │   │
│  │driving_model│ego_lanes    │scene_3d + LiDAR fusion                │   │
│  └─────────────┴─────────────┴─────────────────────────────────────────┘   │
│                              ↓                                              │
│  L1.5: SAFETY PERCEPTION (DORA nodes, Python, 5-10Hz)                       │
│  ├── stop_line, pedestrian, cyclist, road_condition                         │
│  ├── school_zone, work_zone                                                 │
│  └── ALL publish to safety/perception_events                               │
│                              ↓                                              │
│  L1.6: PERCEPTION FUSION (DORA node, Python, 20Hz)                          │
│  └──► Unified PerceptionContext → perception/context                       │
│                              ↓                                              │
│  L2: BEHAVIOR PLANNING (DORA node, Python, 20Hz)                            │
│  └──► ManeuverCommand → planning/maneuver                                  │
│                              ↓                                              │
│  L2.5: TRAJECTORY PLANNING (DORA node, Python, 20Hz)                        │
│  └──► Trajectory → planning/trajectory                                     │
│      (ACADOS Python interface — no C++ node needed)                        │
│                              ↓                                              │
│  L3: CONTROL (DORA node + operators, Python, 100Hz)                         │
│  ├──► Lateral: Torque PID (operator, tracks MPC curvature)                 │
│  └──► Longitudinal: OpenPID (operator, tracks MPC accel)                   │
│      (Camera=30Hz → Planner=20Hz → Controller=100Hz for smoothness)        │
│                              ↓                                              │
│  L4: VEHICLE INTERFACE (ROS2 bridge — simple structs only)                  │
│  └──► CAN frames → Vehicle                                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Package Restructuring (from 150 → ~40 Python modules)

VisionPilot's package explosion is partly due to ROS2's "one node per package" pattern. DORA's operator model allows co-locating related transforms.

#### Sensing Layer (`src/sensing/`)

| VisionPilot (ROS2) | DoraPilot (DORA) | Notes |
|-------------------|------------------|-------|
| `camera_driver` | `camera_node/camera_node.py` | DORA node, V4L2 capture, Python |
| `hesai_driver` | `lidar_node/lidar_node.py` | DORA node, Pandar QT64, Python |
| `stereo_matcher` | `stereo_node/stereo_node.py` | DORA node + SGM operator, Python |
| `image_preprocessor` | **operators inside `camera_node/`** | crop/resize as operators, not separate pkgs |
| `sensing_quality` | `quality_operator.py` | In-process quality analysis |

#### Perception Layer (`src/perception/`)

| VisionPilot (ROS2) | DoraPilot (DORA) | Notes |
|-------------------|------------------|-------|
| `driving_model` | `driving_vision_node/driving_vision_node.py` | NPU node — isolated process, Python |
| `split_model` | `driving_policy_node/driving_policy_node.py` | NPU node — isolated process, Python |
| `lane_detector` | `lane_detection_node/lane_detection_node.py` | NPU node, Python |
| `auto_speed` | `auto_speed_node/auto_speed_node.py` | ONNX/CPU node, Python |
| `lidar_detector` | `lidar_perception_node/lidar_perception_node.py` | Hailo-8 or NPU, Python |
| `perception_fusion` | `perception_fusion_node/perception_fusion_node.py` | CPU node, Python |
| `object_tracker` | `tracker_operator.py` | Lightweight — operator, not node |
| `crop_box_filter`, `voxel_grid_filter` | `filter_operators.py` | In-process pointcloud filters |

**Key insight**: DORA operators eliminate the need for separate `crop_box_filter` and `voxel_grid_filter` packages. They become functions inside a shared operator runtime.

#### Planning Layer (`src/planning/`)

| VisionPilot (ROS2) | DoraPilot (DORA) | Notes |
|-------------------|------------------|-------|
| `behavior_planner` | `behavior_planner_node/behavior_planner_node.py` | CPU node, Python |
| `trajectory_planner` | `trajectory_planner_node/trajectory_planner_node.py` | ACADOS Python interface |
| `longitudinal_planner` | merged into `trajectory_planner_node` | Simplify — one MPC node |
| `lateral_planner` | merged into `trajectory_planner_node` | Simplify |
| `velocity_smoother` | `smoother_operator.py` | Operator for velocity profile filtering |
| `trajectory_comparator` | `trajectory_selector_node/trajectory_selector_node.py` | Selects best from parallel generators |

#### Control Layer (`src/control/`)

| VisionPilot (ROS2) | DoraPilot (DORA) | Notes |
|-------------------|------------------|-------|
| `vehicle_controller` | `controller_node/controller_node.py` | 100Hz control node, Python |
| `trajectory_follower` | `follower_operator.py` | In-process path tracking |
| `lat_control_torque` | `lateral_pid_operator.py` | Operator (in-process) |
| `long_control` | `longitudinal_pid_operator.py` | Operator (in-process) |
| `control_validator` | `control_validator_operator.py` | In-process safety check |

#### System Layer (`src/system/`)

| VisionPilot (ROS2) | DoraPilot (DORA) | Notes |
|-------------------|------------------|-------|
| `inference_ecu` | `inference_daemon/inference_daemon.py` | DORA node exposing NPU/GPU/RGA/MPP |
| `camera_daemon` | `camera_daemon/camera_daemon.py` | DORA node (preserved pattern) |
| `thermal` | `thermal_daemon/thermal_daemon.py` | DORA node |
| `power_manager` | `power_daemon/power_daemon.py` | DORA node |
| `health_monitor` | `health_daemon/health_daemon.py` | DORA node |
| `system_state_manager` | `state_daemon/state_daemon.py` | DORA node |

#### Voice / Navigation / Dashboard

These are **lower-frequency, non-critical-path** modules. Migrate later or keep as ROS2 nodes bridged to DORA.

| Module | Strategy |
|--------|----------|
| Voice (11 pkgs) | Keep ROS2, bridge via `dora-ros2-bridge` |
| Navigation (6 pkgs) | Keep ROS2, bridge via `dora-ros2-bridge` |
| Dashboard (3 pkgs) | Keep ROS2, bridge via `dora-ros2-bridge` |
| BLE/NCP telemetry | Keep ROS2 |

---

## 5. Key DORA Advantages for ADAS

### 5.1 LiDAR + Camera Fusion Performance

LiDAR point clouds are **the critical pain point** in ROS2. A 64-line Pandar QT64 produces ~200,000 points/frame = ~2.4MB at 10Hz.

| Metric | ROS2 DDS | DORA Zenoh SHM |
|--------|----------|----------------|
| **Copy count** | 2-4 copies (publish→DDS→subscribe) | 0 copies (shared memory pointer) |
| **Latency** | 5-15ms (jittery) | <1ms (flat) |
| **CPU usage** | High (serialization threads) | Negligible |
| **RAM pressure** | Multiple buffers per subscriber | Single buffer, reference counted |

**From arxiv 2602.13252v1:** When transmitting 4MB data at 20Hz, DORA maintains **0.82 ms** while ROS2 hits **17.1 ms**. For dorapilot's 20Hz perception pipeline, this means DORA adds **<1ms** communication overhead vs ROS2 adding **>15ms** — almost an entire frame budget.

### 5.2 Parallel Trajectory Generation (A/B Testing)

VisionPilot's `parallel-trajectory-architecture.md` proposes running classical + neural + split models in parallel. In ROS2, this requires static launch definitions. In DORA:

```bash
# Runtime: add a new trajectory generator for A/B testing
dora node add --from-yaml new_model_node.yml --connect-to trajectory_selector
```

No restart required. The `trajectory_selector` node receives a new input dynamically.

### 5.3 Record/Replay for Regression Testing

```bash
# Record a drive
dora record dataflow.yml --output drive_001.drec

# Replay with a NEW driving model substituted
dora replay drive_001.drec \
  --substitute driving_vision:new_vision_model.py \
  --speed 2.0
```

This is impossible with ROS2 bags without manual bag filtering/remapping.

### 5.4 Fault Tolerance

DORA has per-node restart policies:

```yaml
nodes:
  - id: driving_vision
    path: driving_vision_node.py
    restart_policy: on_failure
    max_restarts: 3
    backoff: exponential
```

If the NPU inference node crashes (e.g., thermal throttling), DORA restarts it automatically. ROS2 nodes crash silently unless wrapped by external watchdogs.

### 5.5 Resource Monitoring

```bash
# Real-time TUI showing per-node CPU, memory, queue depth, network I/O
dora top

# JSON snapshot for telemetry integration
dora top --once > /tmp/system_health.json
```

---

## 6. Python-First Implementation (No C++ Application Code)

### 6.1 Standard Node Pattern

All dorapilot nodes use the Python `dora.Node` API:

```python
from dora import Node
import pyarrow as pa
import numpy as np
import json

class LidarPerceptionNode:
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
        # Zero-copy: PyArrow array → numpy view
        data = event["value"].to_numpy().view(np.uint8)
        points = np.frombuffer(data, dtype=np.float32).reshape(-1, 4)
        
        objects_3d = self.model.infer(points)
        result_json = json.dumps(objects_3d)
        self.node.send_output("objects_3d", pa.array([result_json]))

    def load_rknn_model(self):
        from rknnlite.api import RKNNLite
        rknn = RKNNLite()
        rknn.load_rknn("/data/models/pointpillars_rk3688.rknn")
        rknn.init_runtime(core_mask=RKNNLite.NPU_CORE_1)
        return rknn

if __name__ == "__main__":
    node = LidarPerceptionNode()
    node.run()
```

### 6.2 Operator Pattern

```python
# In-process operator for zero-overhead transforms
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
        
        send_output("points_filtered", pa.array(filtered.tobytes()))
```

### 6.3 ACADOS MPC (Python Interface — No C++ Node)

VisionPilot's trajectory planner uses ACADOS via its Python interface. This is preserved unchanged:

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
        
        # Solve MPC (generated C solver, called from Python)
        status = self.solver.solve()
        trajectory = self.solver.get(1, "x")
        return trajectory
```

The generated C solver is a shared library (`.so`) loaded by Python. No C++ node is needed. This is the standard ACADOS workflow.

### 6.4 No Build Step for Application Code

```bash
# VisionPilot: build everything
cd ~/pilot/visionpilot && colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release

# DoraPilot: just install dora-rs and run
pip install dora-rs
dora run dataflows/dorapilot_main.yml
```

No `CMakeLists.txt`. No `package.xml`. No `setup.py` for nodes. Python scripts execute directly.

---

## 7. Migration Strategy (Python-Only)

### Phase 1: Foundation (Weeks 1-4)

1. **Bootstrap DORA** on RK3688: `pip install dora-rs`, verify `dora run` works
2. **Port inference HAL**: Convert `system/inference_ecu` to DORA node `inference_daemon` (Python layer unchanged)
3. **Single pipeline**: camera → preprocess (operators) → driving_vision (Python node) → ros2_bridge → vehicle
4. **Validate** end-to-end with `dora top` monitoring

### Phase 2: Perception (Weeks 5-10)

1. Migrate `perception/driving_model` → `driving_vision_node` (Python, RKNNLite API)
2. Migrate `perception/lane_detector` → `lane_detection_node` (Python)
3. Add LiDAR pipeline: `lidar_node` (Python) → filter operators (Python) → `lidar_perception_node` (Python)
4. Sensor fusion: `perception_fusion_node` consuming camera + LiDAR via Zenoh SHM (Python)

### Phase 3: Planning + Control (Weeks 11-16)

1. Migrate `planning/trajectory_planner` → `trajectory_planner_node` (Python + ACADOS Python interface)
2. Migrate `control/vehicle_controller` → `controller_node` (Python)
3. Convert PID controllers to operators for 100Hz low-latency tracking (Python)
4. Validate 20Hz planning + 100Hz control timing

### Phase 4: Safety + Production (Weeks 17-24)

1. Migrate safety nodes (AEB, FCW, BSD) to DORA with `restart_policy: always` (Python)
2. Create separate `dorapilot_safety.yml` dataflow for isolation
3. Add circuit breakers and input timeouts for safety-critical paths
4. Record/replay validation suite
5. Performance benchmarking: DORA vs ROS2 latency, jitter, CPU usage

### Phase 5: Gradual Non-Critical Migration (Ongoing)

1. Voice stack: keep ROS2, bridge to DORA
2. Navigation: keep ROS2, bridge to DORA
3. Dashboard: keep ROS2, bridge to DORA
4. Eventually migrate if latency requirements tighten

---

## 8. Best Practices from dora-autoware (Ported to Python)

### 8.1 Lesson: Python API is Production-Ready
The dora-autoware project ported NDT localization, object detection, and planning to DORA using the **Python API** — not C++. The Rust core handles IPC; Python handles algorithm logic. This is the intended pattern.

### 8.2 Lesson: Numpy Byte Parsing Replaces C++ Parsers
Instead of writing a C++ node to parse LiDAR bytes, use numpy:
```python
data = event["value"].to_numpy().view(np.uint8)
points = np.frombuffer(data, dtype=np.float32).reshape(-1, 4)
```
This is C-speed underneath (numpy is C) and eliminates a C++ node entirely.

### 8.3 Lesson: Keep LiDAR 100% DORA-Native
The dora-autoware team discovered the ROS2 bridge **panics on PointCloud2 struct arrays**. Their solution: never bridge LiDAR data. Dorapilot adopts this as a hard rule.

### 8.4 Lesson: Separate Safety Dataflow
Autoware's safety-critical modules run in an **independent dataflow** so main pipeline restarts don't affect AEB/MRM. Dorapilot uses `dorapilot_safety.yml` separate from `dorapilot_main.yml`.

### 8.5 Lesson: Start with Python Dicts, Migrate to Arrow Schemas Later
Dora-autoware started with simple Python dictionaries for message passing and gradually added Arrow schema validation. Dorapilot follows the same path: prototype with `dict`, formalize with Arrow once stable.

---

## 9. Risk Analysis (Python-Native, Updated)

| Risk | Severity | Mitigation |
|------|----------|------------|
| **DORA ROS2 bridge maturity** (experimental, PointCloud2 panic) | 🔴 High | Do NOT bridge LiDAR. Bridge only simple structs at vehicle boundary. Follow dora-autoware pattern. |
| **Python performance for heavy compute** | 🟢 Low | Numpy-vectorized ops run at C speed. NPU via RKNNLite Python API. ACADOS via Python interface. GIL is not a bottleneck for these patterns. |
| **NPU driver integration** | 🟢 Low | Preserve existing HAL (`npu_rockchip.py`) behind `inference_daemon`. No driver rewrite. |
| **Safety certification** | 🟡 Medium | DORA's deterministic dataflow is architecturally better, but no precedents yet. Document timing budgets rigorously. |
| **Hot reload in safety-critical code** | 🟡 Medium | Disable hot reload for AEB/MRM nodes. Use `restart_policy: never` in production. |
| **Coordinator HA partial reclaim** | 🟡 Medium | Run coordinator as systemd `Restart=always`. Split safety-critical subsystems into independent `dora run` dataflows. |
| **Message schema migration (Arrow)** | 🟢 Low | Start with Python dict + PyArrow arrays. No IDL compilation needed. Migrate to strict schemas incrementally. |
| **Community size & long-term support** | 🟡 Medium | DORA is Apache-2.0. Fork if needed. Track GOSIM/autoware adoption as health indicators. |
| **Team expertise (Rust)** | 🟢 Low | **Not needed for application code.** Daily development is 100% Python. Only DORA internals use Rust. |

**Removed risks (Python-native stance eliminates them):**
- ❌ C++ API maturity — not applicable; we use Python API
- ❌ CMake/build complexity — not applicable; `pip install dora-rs`
- ❌ Cross-compilation — not applicable for Python-only app code

---

## 10. Foundry Concepts from VisionPilot to Preserve

| VisionPilot Concept | DoraPilot Adaptation |
|--------------------|----------------------|
| **3-layer boundary** (App/System/3rdParty) | Preserve: operators/nodes → daemon → HAL → drivers |
| **Functional naming** (`npu_rockchip`, not `rknn_backend`) | Preserve: `npu_rockchip_node`, `dmu_rga_operator` |
| **Topic naming** (`/<layer>/<pkg>/<data>`) | Map to DORA output IDs: `camera/image`, `perception/context` |
| **Daemon pattern** (`camera_daemon`, `thermal_daemon`) | Preserve: DORA nodes with `_daemon` suffix for hardware exclusivity |
| **Budget-based NPU allocation** (85% TOPS safety line) | Preserve: `inference_daemon` manages core allocation |
| **MPC + PID two-layer control** (20Hz + 100Hz) | Preserve: `trajectory_planner_node` (20Hz) + `controller_node` (100Hz with operators) |
| **Param YAML convention** (`.param.yaml`) | Replace with DORA node `env:` in `dataflow.yml` + environment overrides |
| **Unit suffixes** (`_mps`, `_deg`, `_rad`) | Preserve in Python dict keys |

---

## 11. Open Questions for Team Discussion

1. **Should dorapilot support RK3576 (6 TOPS) or RK3688-only (12 TOPS)?**  
   DORA's lower overhead helps RK3576, but LiDAR fusion likely requires RK3688.

2. **Should we keep `evp_msgs` ROS message definitions or migrate to Python dicts + Arrow?**  
   Python dicts enable fastest prototyping. Arrow schemas add validation but require more design.

3. **Should the split Vision+Policy architecture (OpenPilot 0.10.x) be the default in v1.0?**  
   VisionPilot currently uses single-stage; DORA's dataflow naturally supports the split model.

4. **How deep should the ROS2 bridge go?**  
   Option A: Bridge only at vehicle/actuator boundary.  
   Option B: Bridge all non-critical modules (voice, nav, dashboard).  
   Option C: Full migration (no ROS2).

5. **Should we use DORA operators for the 100Hz control loop?**  
   Operators run in-process with the runtime, offering <100µs latency, but a crash in any operator crashes the runtime. For safety, keep PID controllers as operators within a dedicated `control_runtime` node.

---

## 12. Reference Documents

- **arxiv 2602.13252v1** — "DORA: Dataflow Oriented Robotic Architecture" (Feb 2026). Peer-reviewed benchmark vs ROS1/ROS2/CyberRT.
- **github.com/dora-rs/dora-benchmark** — CPU/GPU benchmark suite. Shows ROS2 failing at 40MB.
- **github.com/dora-rs/dora-autoware** — Autoware porting to DORA. Real vehicle deployment. Python API usage.
- **github.com/dora-rs/dora-drives** — CARLA-based autonomous driving tutorial.
- **github.com/dora-rs/dora** — Core framework.
- **china2024.gosim.org** — GOSIM 2024 presentation on DORA in autonomous driving.
- VisionPilot: `docs/architecture/layer-boundaries.md`
- VisionPilot: `docs/architecture/HARDWARE_INFERENCE_ARCHITECTURE.md`
- VisionPilot: `docs/control/README.md`
- VisionPilot: `docs/perception/README.md`
- VisionPilot: `docs/architecture/parallel-trajectory-architecture.md`

---

*Research completed 2026-05-30. Python-Native Edition. Ready for architecture review and Phase 1 planning.*
