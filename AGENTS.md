# DoraPilot Agent Instructions

This file governs all Kimi agent behavior in this repository and its subdirectories.

When a skill is triggered (see Triggers below), read and apply the referenced `.claude/skills/**/*.md` file in full. Do not paraphrase or skip sections.

---

## Triggers — Auto-apply on match

| Trigger condition | Skill to apply | Source file |
|---|---|---|
| User reports a bug, says something is broken/throwing/failing, asks to debug/diagnose/investigate, or pastes a stack trace / error log | **debug-mantra** | `.claude/skills/engineering/debug-mantra/SKILL.md` |
| User asks to review, audit, sanity-check, or get a second opinion on a plan, PR, diff, design doc, or proposed code change | **scrutinize** | `.claude/skills/engineering/scrutinize/SKILL.md` |
| User says "write the post-mortem / postmortem / RCA / root cause analysis", "document this fix", "write up the root cause", "close out this bug with a writeup", or hands you a fixed-and-validated bug and asks for the writeup | **post-mortem** | `.claude/skills/engineering/post-mortem/SKILL.md` |
| User asks to write/rewrite for management / exec / VP / director / PM / release manager, asks for "executive summary / leadership update / status update", says "make this less technical / less jargony", or asks for a slack / email / standup / meeting version of engineering work | **management-talk** | `.claude/skills/productivity/management-talk/SKILL.md` |

**Rules for triggering:**
- Apply the skill proactively without waiting for explicit user invocation.
- If multiple triggers match, apply the most specific skill first.
- If the user explicitly says "skip the skill" or "don't use X", respect the override.

---

## Project Context

DoraPilot is a next-generation ADAS stack built on **dora-rs** (Dataflow-Oriented Robotic Architecture), succeeding VisionPilot's ROS2-based architecture. Target hardware: ExoPilot 03/03H (RK3688, 12 TOPS NPU, LiDAR-enabled).

**Key architectural difference from VisionPilot:**
- VisionPilot: ROS2 Humble, ~150 packages, DDS pub/sub, Python launch files
- DoraPilot: dora-rs 1.0, ~60 packages, Zenoh SHM zero-copy, declarative YAML dataflows

**Critical design rule:** DORA-native for data-heavy pipelines (camera, LiDAR, perception, planning). ROS2 bridge ONLY at boundaries (vehicle CAN, voice, navigation, dashboard).

---

## DORA Conventions

### Dataflow YAML
- All pipelines defined in `dataflows/*.yml`
- Use `dora/timer/millis/<N>` or `dora/timer/hz/<N>` for timing
- Node IDs: `snake_case`, descriptive (`driving_vision`, not `dv`)
- Output IDs: `snake_case`, noun-based (`image_raw`, `trajectory`)
- Safety-critical nodes MUST specify `restart_policy: never`

### Node Implementation (Python)
```python
from dora import Node
import pyarrow as pa

class MyNode:
    def on_event(self, dora_event, send_output):
        if dora_event["type"] == "INPUT":
            value = dora_event["value"]
            # process...
            send_output("output_name", pa.array(result))
        return DoraStatus.CONTINUE
```

### Operator Implementation (Python)
```python
# Operators run in-process — keep them lightweight and stateless
class MyOperator:
    def on_input(self, dora_input, send_output):
        value = dora_input["value"]
        result = self.transform(value)
        send_output("output_name", pa.array(result))
```

### Topic/Dataflow Path Mapping
- VisionPilot used `/<layer>/<package>/<data>`
- DoraPilot uses `<node_id>/<output_id>` within dataflows
- Bridge to ROS2 topics ONLY at `vehicle_bridge` and `ros2_bridge` nodes

---

## Layer Boundaries (Preserved from VisionPilot)

```
L3 APPLICATION  ──► DORA nodes/operators (sensing, perception, planning, control)
       │            (NO direct hardware imports; use system daemons)
       ▼ DORA inputs/outputs
L2 SYSTEM      ──► DORA daemon nodes (inference_daemon, camera_daemon, etc.)
       │            (HAL + BSP; expose hardware via DORA outputs)
       ▼ direct calls
L1 THIRD_PARTY ──► rknpu2, hef_rt, rockchip_rga, mpp
       │            (ONLY accessed by system/inference_daemon/backends/)
       ▼
   HARDWARE
```

**Boundary Rules:**
1. Application nodes CANNOT import from `system.*` or `third_party.*`
2. System daemons CANNOT import from application layers
3. Only `system/inference_daemon/backends/` accesses third_party libraries
4. ROS2 bridge nodes are the ONLY exception for cross-boundary communication

---

## Naming Conventions

| Element | Format | Example |
|---------|--------|---------|
| Dataflow file | `dorapilot_<purpose>.yml` | `dorapilot_main.yml` |
| Node package | `src/<layer>/<name>_node/` | `src/perception/driving_vision_node/` |
| Operator file | `src/<layer>/operators/<name>.py` | `src/sensing/operators/image_preprocess.py` |
| Daemon package | `src/system/<name>_daemon/` | `src/system/inference_daemon/` |
| Node class | `PascalCase` + `Node` | `DrivingVisionNode` |
| Node ID in YAML | `snake_case` | `driving_vision` |
| Model files | `/data/models/<platform>/<name>.rknn` | `/data/models/rk3688/driving_vision.rknn` |

---

## Safety-Critical Rules

- Any diff touching `src/safety/` requires scrutiny of BOTH activation and de-activation paths
- AEB, FCW, MRM nodes MUST use `restart_policy: never` in dataflow YAML
- Safety dataflow (`dorapilot_safety.yml`) runs independently from main pipeline
- Hot reload is DISABLED for safety nodes
- All safety nodes MUST implement input timeout circuit breakers

---

## Hardware Abstraction

### Inference Daemon (`src/system/inference_daemon/`)

The inference_daemon replaces VisionPilot's `system/inference_ecu`:

```python
# Backends (unchanged HAL from VisionPilot)
backends/
├── npu_rockchip.py      # RKNN runtime
├── npu_hailo.py         # Hailo-8L runtime
├── dmu_rga.py           # RGA 2D accelerator
├── vpu_mpp.py           # MPP video codec
└── cpu_acl.py           # CPU fallback
```

**Services exposed as DORA outputs:**
- `inference_daemon/inference_result` — inference output
- `inference_daemon/backend_status` — NPU/GPU health

### NPU Budget (RK3688)

| Core | TOPS | Allocation | Budget |
|------|------|------------|--------|
| Core 0 | 6.0 | driving_vision + driving_policy | 5.0 (83%) |
| Core 1 | 6.0 | lane_detection + lidar_perception + scene_3d | 5.0 (83%) |

**Safety line:** 85% TOPS per core. Never exceed.

---

## Development Workflow

### Local Dev Loop

```bash
# Run single dataflow locally (no coordinator needed)
dora run dataflows/dorapilot_main.yml --verbose

# Validate YAML before running
dora validate dataflows/dorapilot_main.yml

# Visualize dataflow
dora graph dataflows/dorapilot_main.yml --output graph.html
```

### Testing with Record/Replay

```bash
# Record sensor data
dora record dataflows/dorapilot_main.yml --output test_drive.drec

# Replay with new algorithm
dora replay test_drive.drec --substitute driving_vision:new_model.py
```

### Monitoring

```bash
# Live resource monitor
dora top

# Topic frequency
dora topic hz camera/image_raw

# Topic inspection
dora topic echo perception/context
```

---

## General Operating Rules

- **Minimal changes** — Make the smallest change that achieves the goal.
- **Follow existing style** — Match the codebase's patterns and conventions.
- **Test what you build** — Run `dora validate` after YAML changes. Test dataflows before committing.
- **Never commit git mutations** unless explicitly asked. Ask for confirmation every time.
- **One iteration is normal, three is a smell** — If still revising on the third pass, ask what assumption is wrong.

---

*AGENTS.md v1.0 — 2026-05-30*
