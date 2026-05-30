# DoraPilot 🚗⚡

**Next-generation ADAS stack for ExoPilot 03+ — powered by dora-rs**

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![DORA](https://img.shields.io/badge/Middleware-dora--rs%201.0-orange.svg)]()
[![Platform](https://img.shields.io/badge/Platform-RK3688-green.svg)]()
[![Language](https://img.shields.io/badge/Language-Python%203.10+-blue.svg)]()

DoraPilot is the successor to [VisionPilot](https://github.com/exo-electronics/visionpilot), re-architected on **dora-rs** (Dataflow-Oriented Robotic Architecture) for 10-31× faster IPC, zero-copy LiDAR fusion, and declarative pipeline definitions.

> **Philosophy:** Best of both worlds. Autoware directory conventions + VisionPilot ADAS logic + DORA zero-copy performance. Python-only. No build step.

---

## Why DoraPilot?

| | VisionPilot (ROS2) | **DoraPilot (DORA)** |
|---|---|---|
| **LiDAR IPC Latency** | 15-20ms (DDS serialization) | **<1ms** (Zenoh SHM zero-copy) |
| **Camera → Control Pipeline** | ~60ms end-to-end | **~46ms** end-to-end |
| **Build Step** | `colcon build` (8-15 min on RK3688) | **None** — Python runs directly |
| **Pipeline Definition** | 150 packages, Python launch files | **~40 modules, declarative YAML** |
| **A/B Testing Models** | Restart entire system | **Live node add/remove** |
| **Record/Replay** | MCAP bags (no substitution) | **`.drec` + node substitution** |
| **Fault Tolerance** | External systemd watchdogs | **Built-in restart policies** |
| **Messages** | `evp_msgs` (requires `rosidl` build) | **`drp_msgs`** (pure Python, zero compilation) |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    DORA DATAFLOW (Zero-Copy)                │
│                                                             │
│   Camera ──► Image Preprocess ──► Driving Vision ──┐        │
│      │                              (NPU Core 0)   │        │
│   LiDAR ──► PointCloud Filter ──► LiDAR Detector ──┼──► Perception Fusion
│      │                              (NPU Core 1)   │      (PerceptionContext)
│   GNSS ────────────────────────────────────────────┘        │
│   IMU ─────────────────────────────────────────────┘        │
│                                                             │
│   PerceptionContext ──► Behavior Planner ──► Trajectory     │
│                                                Planner      │
│                                                  │          │
│   Trajectory Selector ◄── Classical + Neural    │          │
│          │                                       │          │
│   Controller (100Hz PID) ◄───────────────────────┘          │
│          │                                                  │
│          ▼                                                  │
│   Vehicle Bridge (ROS2) ──► CAN ──► Vehicle                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

- **DORA-native**: sensing, perception, planning, control — all Python, zero-copy
- **ROS2 bridge**: vehicle interface only (CAN, simple structs)
- **Safety isolation**: AEB/FCW/MRM run in separate `dorapilot_safety.yml`
- **drp_msgs**: pure-Python message definitions, ROS2-compatible naming

---

## Project Structure

```
dorapilot/
├── dataflows/
│   └── dorapilot_main.yml          # Main ADAS pipeline (declarative)
├── src/
│   ├── drp_msgs/                   # Message definitions (pure Python)
│   │   ├── std_msgs.py             # Header, Time, String, Bool...
│   │   ├── sensor_msgs.py          # Image, PointCloud2, Imu, NavSatFix
│   │   ├── perception_msgs.py      # PerceptionContext, DetectedObject...
│   │   ├── planning_msgs.py        # Trajectory, ManeuverCommand
│   │   ├── control_msgs.py         # LateralCommand, LongitudinalCommand
│   │   └── utils.py                # to_arrow(), from_arrow()
│   ├── sensing/                    # Camera, LiDAR, GNSS, IMU
│   ├── perception/                 # NPU inference + fusion
│   ├── planning/                   # Behavior + trajectory MPC
│   ├── control/                    # 100Hz PID controller
│   ├── safety/                     # AEB, FCW, MRM
│   ├── system/                     # Inference daemon, camera daemon...
│   └── vehicle_bridge/             # ROS2 bridge (vehicle boundary)
└── docs/
    ├── architecture/
    │   └── DORAPILOT_PROPOSED_ARCHITECTURE.md
    └── research/
        ├── DORA_MIGRATION_RESEARCH.md
        ├── DORA_PROS_CONS.md
        └── VISIONPILOT_TO_DORA_MIGRATION_GUIDE.md
```

---

## Quick Start

### Prerequisites

```bash
# Ubuntu 22.04 LTS (ARM64)
# Python 3.10+
# RK3688 with NPU drivers (rknpu2)
```

### Install

```bash
# DORA CLI + Python API
pip install dora-rs numpy pyarrow

# Verify
dora --version
```

### Run a Single Node

```bash
cd ~/pilot/dorapilot

# Run lidar capture node standalone
dora run dataflows/dorapilot_main.yml --node lidar
```

### Run Full Pipeline

```bash
# Development mode (no coordinator, console output)
dora run dataflows/dorapilot_main.yml --verbose

# Production mode
dora up
dora start dataflows/dorapilot_main.yml --name dorapilot_main --attach

# Monitor
dora top
```

### Validate Dataflow

```bash
# Check YAML syntax and node connectivity
dora validate dataflows/dorapilot_main.yml

# Generate visual graph
dora graph dataflows/dorapilot_main.yml --output graph.html
```

---

## drp_msgs — Messages Without Compilation

```python
from drp_msgs import Header, PointCloud2, PerceptionContext
from drp_msgs.utils import to_arrow, from_arrow

# Create message (same API as ROS2, but pure Python)
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
print(ctx.lead.distance_m)  # 45.2
```

**No `colcon build`. No `rosidl`. No `package.xml`.** Import and use.

See [`src/drp_msgs/README.md`](src/drp_msgs/README.md) for full API.

---

## Node Development

### Minimal Node (Python)

```python
#!/usr/bin/env python3
from dora import Node
from drp_msgs import PerceptionContext
from drp_msgs.utils import to_arrow, from_arrow

class MyNode:
    def __init__(self):
        self.node = Node()

    def run(self):
        for event in self.node:
            if event["type"] == "INPUT":
                ctx = from_arrow(event["value"], PerceptionContext)
                result = self.process(ctx)
                self.node.send_output("result", to_arrow(result))
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
      perception_context: perception_fusion/perception_context
    outputs:
      - result
```

---

## Hardware Targets

| Platform | SoC | NPU | Cameras | LiDAR | Status |
|----------|-----|-----|---------|-------|--------|
| **ExoPilot 03** | RK3688 | 12 TOPS | 5× + telephoto | Pandar QT64 | 🎯 Target |
| **ExoPilot 03H** | RK3688 | 12 TOPS + premium | 5× + driver cam | Pandar QT64 | 🎯 Target |

---

## Documentation

| Document | What it covers |
|----------|---------------|
| **[DEVELOPMENT.md](DEVELOPMENT.md)** | Practical guide: write a node, add a message, run a dataflow |
| **[docs/architecture/DORAPILOT_PROPOSED_ARCHITECTURE.md](docs/architecture/DORAPILOT_PROPOSED_ARCHITECTURE.md)** | Full architecture v2.0, dataflow YAMLs, performance budgets |
| **[docs/research/DORA_MIGRATION_RESEARCH.md](docs/research/DORA_MIGRATION_RESEARCH.md)** | Why DORA, benchmarks, migration phases, risk analysis |
| **[docs/research/DORA_PROS_CONS.md](docs/research/DORA_PROS_CONS.md)** | Detailed comparison, decision matrix, best practices |
| **[docs/research/VISIONPILOT_TO_DORA_MIGRATION_GUIDE.md](docs/research/VISIONPILOT_TO_DORA_MIGRATION_GUIDE.md)** | Line-by-line migration patterns from ROS2 to DORA |
| **[src/drp_msgs/README.md](src/drp_msgs/README.md)** | Message API reference for developers |

---

## Project Status

| Phase | Status | Description |
|-------|--------|-------------|
| Research | ✅ Complete | DORA evaluated, benchmarks validated |
| Architecture v2.0 | ✅ Complete | Hybrid Autoware + VisionPilot baseline |
| drp_msgs | ✅ Complete | Pure-Python message system |
| Node skeletons | ✅ Complete | All layers have placeholder nodes |
| Phase 1: Sensing | ⏳ Active | Camera V4L2, Pandar QT64 parser |
| Phase 2: Perception | ⏳ Pending | Port RKNN models, implement fusion |
| Phase 3: Planning/Control | ⏳ Pending | ACADOS MPC, PID controller |
| Phase 4: Safety | ⏳ Pending | AEB/FCW/MRM isolated dataflow |
| Phase 5: Vehicle Testing | ⏳ Pending | ROS2 bridge, on-road validation |

---

## License

Apache 2.0

## Acknowledgments

- [VisionPilot](https://github.com/exo-electronics/visionpilot) — Proven ADAS foundation
- [dora-rs](https://github.com/dora-rs/dora) — Next-gen robotics middleware
- [Autoware](https://github.com/autowarefoundation/autoware) — Architecture patterns

---

**DoraPilot** — Smaller latency, cleaner architecture, safer driving.
