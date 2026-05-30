# DORA vs ROS2: Pros & Cons for DoraPilot ADAS — Python-Native Stance

**Date:** 2026-05-30  
**Research Source:** arxiv paper (Feb 2026), dora-rs GitHub, dora-benchmark, dora-autoware, community discussions, GOSIM 2024 presentations  
**Context:** Next-gen ADAS stack for ExoPilot 03+ (RK3688, LiDAR, 12 TOPS NPU)  
**Language Stance:** Python 3.10+ for all application nodes. No C++ application code.

---

## TL;DR Scorecard

| Category | DORA Score | ROS2 Score | Winner |
|----------|-----------|------------|--------|
| **IPC Performance (small data)** | ★★★★★ | ★★★★☆ | DORA (slight) |
| **IPC Performance (large data / LiDAR)** | ★★★★★ | ★★☆☆☆ | DORA (massive) |
| **Developer Experience (YAML)** | ★★★★★ | ★★★☆☆ | DORA |
| **Ecosystem Maturity** | ★★★☆☆ | ★★★★★ | ROS2 |
| **Production Reliability** | ★★★★☆ | ★★★★☆ | Tie |
| **Observability** | ★★★★★ | ★★★☆☆ | DORA |
| **Record/Replay & Testing** | ★★★★★ | ★★★☆☆ | DORA |
| **Real-time & Safety** | ★★★★☆ | ★★★☆☆ | DORA |
| **Multi-machine / V2X** | ★★★★★ | ★★★☆☆ | DORA |
| **Team Ramp-up (Python-only)** | ★★★★☆ | ★★★★★ | ROS2 (slight) |
| **Edge SoC Support (ARM64)** | ★★★★☆ | ★★★★★ | ROS2 (slight) |

---

## Why DORA for DoraPilot (The VisionPilot Successor Story)

VisionPilot proved a Python-centric ADAS stack can run on RK3588/RK3688 edge SoC. It worked. But ROS2 became the bottleneck — not Python, not the NPU, not the models. **ROS2's DDS serialization is the tax**.

### The One Problem DORA Solves

| Scenario | VisionPilot (ROS2) | DoraPilot (DORA) |
|----------|-------------------|------------------|
| LiDAR pointcloud (2.4MB) camera→fusion | 5–15ms jittery latency, 15–20% CPU core wasted on serialization | <1ms flat latency, **0% CPU** on IPC |
| A/B test two driving models | Restart entire system | `dora node add` at runtime |
| Regression test new model | Re-record ROS bag, no substitution | `dora replay --substitute driving_vision:new_model.py` |
| Debug pipeline on vehicle | Dig through 150 packages, nested launch files | Single `dataflow.yml` + `dora top` |

**DORA does not replace Python. DORA replaces ROS2.** All of VisionPilot's Python code — NPU inference, MPC planning, PID control — stays Python. Only the middleware changes.

---

## What Changes from VisionPilot

### Architectural Changes

| Dimension | VisionPilot (ROS2) | DoraPilot (DORA) |
|-----------|-------------------|------------------|
| **IPC** | DDS CDR serialization (copies data) | Zenoh SHM zero-copy (passes pointers) |
| **Pipeline config** | 150 packages + nested Python launch files | Declarative `dataflow.yml` |
| **Build system** | colcon + CMake + package.xml | `pip install dora-rs` — no build step for app code |
| **Node language** | Python + C++ wrappers (mixed) | **Python only** — no C++ application nodes |
| **Message format** | ROS2 `.msg` IDL → CDR | Apache Arrow → zero deserialization |
| **Record/replay** | MCAP bag, no node substitution | `.drec` with `--substitute` for regression testing |
| **Observability** | `ros2 topic hz` + external Grafana | `dora top`, `dora trace view` built-in |
| **Topology changes** | Static at launch | Dynamic: `dora node add/remove/connect` live |

### What Does NOT Change

- **Python application code** — all inference, planning, control logic stays Python
- **ACADOS MPC** — same Python interface (`gen_long_mpc.py`), same generated C solver
- **RKNN/Hailo models** — same `.rknn`/`.hef` files, same inference flow
- **3-layer boundary** (App / System / Third_Party) — preserved
- **Daemon pattern** (`camera_daemon`, `thermal_daemon`) — preserved
- **MPC + PID two-layer control** (20Hz + 100Hz) — preserved
- **NPU budget allocation** (85% TOPS safety line) — preserved

---

## ✅ PROS — Why DORA Wins for DoraPilot

### 1. Zero-Copy IPC: The LiDAR Killer Feature

**The numbers from the arxiv paper (Feb 2026, peer-reviewed):**

| Payload | Frequency | DORA Latency | ROS2 Latency | DORA Advantage |
|---------|-----------|--------------|--------------|----------------|
| 4 MB (RGB cam) | 20 Hz | **0.824 ms** | 17.112 ms | **20.8× faster** |
| 4 MB | 50 Hz | **0.784 ms** | 4.947 ms | **6.3× faster** |
| 4 MB | 200 Hz | **0.728 ms** | 4.947 ms | **6.8× faster** |
| 32 MB (LiDAR burst) | 50 Hz | **2.78 ms** | 87 ms | **31.3× faster** |
| 1→4 subscribers | 50 Hz | **<1 ms** | 15.3 ms | **15×+ faster** |
| 4→1 fusion | 50 Hz | **1–5 ms** | ~50 ms | **10–50× faster** |

**Real-world robot arm benchmark:**
- DORA: ~1.5 ms average
- ROS2: ~22.0 ms average (**14.7× slower**)

**Why this matters for dorapilot:**
- Pandar QT64 LiDAR: ~200,000 points/frame ≈ 2–3 MB at 10 Hz
- In ROS2, PointCloud2 serialization/deserialization consumes **15–20% of a CPU core** just moving data between nodes
- In DORA, the same data is a **shared memory pointer pass** — zero CPU, zero latency jitter
- This directly translates to: more TOPS for inference, not wasted on IPC

### 2. Flat Latency Curve — Predictable Real-Time

ROS2 latency scales **quadratically-ish** with payload size due to CDR serialization. At 4 MB, ROS2 C++ goes from ~300 µs (small data) to **21 ms** — a 70× blow-up. ROS2 Python fails entirely at 40 MB (message drops).

DORA maintains **<3 ms** for any payload up to 32 MB locally, and <90 ms over LAN. This predictability is critical for ADAS control loops.

```
Latency vs Payload (local, 50Hz):
ROS2:  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  (spikes to 87ms)
DORA:  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  (flat ~2.8ms)
```

### 3. Declarative Dataflows — Launch Files Are Code Smell

VisionPilot has **150+ packages** orchestrated via nested Python launch files. DORA replaces this with:

```yaml
# One readable YAML = entire pipeline
nodes:
  - id: camera
    path: camera_node.py
    outputs: [image]
  - id: lidar
    path: lidar_node.py
    outputs: [points]
  - id: fusion
    path: perception_fusion.py
    inputs:
      image: camera/image
      points: lidar/points
    outputs: [context]
```

**Benefits:**
- No `import launch` boilerplate
- No parameter YAML scattering
- Visualize with `dora graph dataflow.yml` → interactive HTML
- Static validation with `dora validate`

### 4. Dynamic Topology — A/B Test Driving Models Without Reboot

```bash
# Live: add a new trajectory generator for A/B testing
dora node add --from-yaml new_model.yml --connect-to trajectory_selector

# Live: disconnect a failed node
dora node disconnect old_model trajectory_selector
```

VisionPilot's parallel-trajectory-architecture.md proposes running classical + neural + split models in parallel. In ROS2, this requires restarting the entire system. In DORA, it's a CLI command.

### 5. Record/Replay with Node Substitution

```bash
# Record a real drive
dora record dataflow.yml --output drive_001.drec

# Replay with a NEW model, at 2× speed, substituting the driving model
dora replay drive_001.drec \
  --substitute driving_vision:experimental_model.py \
  --speed 2.0
```

ROS2 MCAP bags cannot substitute nodes. You must re-record or filter bags. DORA's `.drec` format enables **true regression testing**: same sensor inputs, different algorithms.

### 6. Built-in Fault Tolerance — No External Watchdog Needed

```yaml
nodes:
  - id: driving_vision
    path: driving_vision.py
    restart_policy: on_failure   # or always / never
    max_restarts: 3
    backoff: exponential
    input_timeout:
      image: 100ms              # circuit breaker
```

In VisionPilot, a crashed NPU inference node requires an external `systemd` restart or manual intervention. DORA handles this natively.

### 7. Observability — `dora top` Beats `ros2 topic hz`

| Command | What it shows |
|---------|---------------|
| `dora top` | Per-node CPU%, memory, queue depth, network I/O, restart count, health |
| `dora topic hz <topic>` | TUI frequency analyzer |
| `dora topic echo <topic>` | Live data print |
| `dora trace view <id>` | Distributed trace spans (no external infra) |
| `dora top --once` | JSON snapshot for telemetry integration |

ROS2 requires: `ros2 topic hz` (basic), `ros2 doctor` (basic), external Prometheus/Grafana (advanced). DORA ships with production observability out of the box.

### 8. Soft Real-Time Support

```yaml
nodes:
  - id: controller
    path: controller.py
    cpu_affinity: [2, 3]        # Pin to isolated cores
    env:
      DORA_RT: "1"             # mlockall + SCHED_FIFO
```

ROS2 has no built-in real-time pinning. You must wrap nodes with `taskset`/`chrt` manually. DORA's `--rt` flag + `cpu_affinity` YAML key make this declarative.

### 9. Multi-Machine / V2X Ready

DORA uses **Zenoh** for distributed communication. This is the same protocol being positioned for automotive V2X (Vehicle-to-Everything). From GOSIM 2024:

> "Eclipse Zenoh has been identified as a key protocol in automotive, from in-vehicle communication to Vehicle-to-Everything applications."

ROS2 distributed requires DDS discovery tuning, multicast, domain IDs, and firewall hell. DORA: `dora cluster up cluster.yml` — SSH-based, label scheduling, rolling upgrades.

### 10. Operator Model — Eliminate Micro-Package Bloat

VisionPilot has separate packages for `crop_box_filter` and `voxel_grid_filter`. In DORA, these become **operators** — lightweight functions inside a shared runtime:

```python
# operator: crop_box_filter.py
import pyarrow as pa
import numpy as np

class CropBoxFilter:
    def on_input(self, dora_input, send_output):
        data = dora_input["value"].to_numpy().view(np.uint8)
        points = np.frombuffer(data, dtype=np.float32).reshape(-1, 4)
        filtered = points[(points[:,0] > self.x_min) & (points[:,0] < self.x_max)]
        send_output("filtered", pa.array(filtered.tobytes()))
```

No `package.xml`, no `setup.py`, no node overhead. Just a Python function.

---

## ❌ CONS — Risks & Limitations of DORA

### 1. Ecosystem Immaturity — The "Node Hub" Gap

ROS2 has **15+ years** of ecosystem: Nav2, MoveIt, rviz2, foxglove, autoware.universe, 10,000+ packages on rosdistro.

DORA has:
- Core framework: mature (1.0 released, production-ready claims)
- Node ecosystem: **immature**. No centralized "Node Hub" equivalent to PyPI/apt/rosdistro
- Community: smaller, mostly research/AI robotics

**Quote from dora-rs discussion #999 (May 2025):**
> "Users need to know where to look for specific functional nodes... There is no unified search and browsing platform... Developers lack a standard process for packaging, describing, and publishing their nodes."

**Impact for dorapilot:**
- We will **re-implement** most ADAS nodes ourselves (which we already do in VisionPilot)
- No free lunch from `apt install ros-humble-nav2-*`
- CAN interface, DBC parsing, vehicle dynamics — all custom code (already custom in VisionPilot)

### 2. ROS2 Bridge Still Experimental — PointCloud2 Issues

The dora-ros2-bridge is marked **experimental** and has known issues:

**GitHub issue (dora-autoware #10, Jan 2024):**
> "Error when trying to publish a PointCloud2 message from dora to ros2... `Struct array's data type is not struct!`"

This is a **blocker-level risk** if we relied on the bridge for LiDAR data. The bridge works for basic types (Image, Twist, Odometry) but complex nested structs (PointCloud2, Path, Trajectory) have Arrow↔ROS2 type conversion bugs.

**Mitigation (from dora-autoware best practice):**
- **Don't bridge LiDAR pointclouds.** Keep LiDAR pipeline 100% DORA-native.
- Bridge only at vehicle boundary: `/actuator/vehicle/command` (simple CAN-like structs)
- This is the pattern dora-autoware successfully used in real-vehicle deployment

### 3. Team Expertise — Python API Masks Rust Internals

| Skill | ROS2 Market | DORA Market |
|-------|-------------|-------------|
| Python robotics dev | Abundant | Abundant (DORA has first-class Python API) |
| C++ robotics dev | Abundant | Abundant (DORA has C++ API, but we don't use it) |
| Rust systems dev | Scarce | Scarce |
| ROS2-specific experience | Very common | Irrelevant |

**Good news:** DORA's Python API is first-class. All dorapilot application nodes are Python. No Rust knowledge needed for daily development.
**Reality check:** Debugging DORA internals (coordinator, daemon, Zenoh SHM edge cases) may require Rust knowledge. If something breaks in `dora-daemon` at 2 AM on a test drive, Rust expertise helps.

**Mitigation:**
- Daily development: 100% Python. Zero Rust required.
- Deep debugging: community support + dora-rs maintainers. Consider having one team member learn Rust for emergencies.

### 4. ARM64 / Embedded Tooling Gaps

DORA claims "first-class" Linux ARM64 support. However:
- Pre-built binaries: available for x86_64 and ARM64
- Python `dora-rs` wheel on ARM64: available but less tested than x86_64
- **No native `apt` packages** for Ubuntu 22.04 ARM64 — must use `pip install dora-rs` or download release ZIP

VisionPilot benefits from Rockchip's Ubuntu 22.04 image with ROS2 Humble pre-installed. DORA requires `pip install`.

**Mitigation:**
- `pip install dora-rs` works on ARM64. Add to setup script.
- No cross-compilation needed for Python-only application code.

### 5. Safety Certification — Unproven vs ROS2

ROS2 has:
- `ros2_rust` with formal methods (`safe_drive`)
- Industrial deployments with safety cases (Autoware, many OEMs)
- Growing body of safety documentation

DORA has:
- Rust = memory safety by default (good)
- No ISO 26262 or ASIL-related documentation yet
- No third-party safety audits published
- "Production-ready" is a self-claim, not independently certified

**For dorapilot:** DORA's deterministic dataflow + explicit timing is architecturally **better** for safety, but we have no precedent to cite to auditors. ROS2 is the devil we know.

### 6. Coordinator as Single Point of Failure (Partial)

DORA 1.0 has **coordinator HA** with redb-backed state persistence. Daemons auto-reconnect. However:

> "Running dataflow reclaim-across-restart is partial, see the open issue tracker."

If the coordinator dies mid-drive, nodes may lose their dataflow graph state. ROS2 has no coordinator — it's fully decentralized (though DDS discovery has its own issues).

**Mitigation for dorapilot:**
- Run coordinator on a separate systemd service with `Restart=always`
- Use `dora run` mode (no coordinator) for safety-critical subsystems
- Or: split into multiple independent dataflows with ROS2 bridge fallback

### 7. Hot Reload is Dangerous for Safety-Critical Code

DORA supports Python operator hot-reload. This is amazing for development but **terrifying** for AEB/FCW/MRM:

> Developer: "Let me hot-reload the braking logic while driving..."

**Mitigation:**
- Disable hot reload in production builds
- Use `restart_policy: never` for safety nodes
- Separate `dev` dataflows from `prod` dataflows

### 8. Message Schema Migration — Arrow vs ROS2 IDL

VisionPilot has **~100 custom message types** in `evp_msgs/` (ROS2 `.msg` / `.srv`).

Migrating to DORA means:
- Option A: Keep ROS2 msg definitions, bridge everything (loses zero-copy benefits)
- Option B: Define Arrow schemas for all messages (significant upfront work)
- Option C: Use Python dictionaries + PyArrow arrays for prototyping, migrate to strict schemas later

**Recommended for dorapilot (Python-only):** Start with Option C. Use Python `dict` with Arrow arrays for data. No need for IDL compilation. Migrate to strict Arrow schemas once dataflow stabilizes.

### 9. Community Size & Support Risk

| Metric | ROS2 | DORA |
|--------|------|------|
| GitHub stars (core) | ~3,500 (ros2) | ~2,500 (dora-rs) |
| Discussions / issues volume | Massive | Small but responsive |
| Commercial support | Multiple vendors (Open Robotics, Tier IV, etc.) | Mostly community |
| Conference presence | IROS, ICRA, ROSCon everywhere | FOSIM, GOSIM, smaller |

If dora-rs development slows or pivots, dorapilot is exposed. ROS2 is backed by the Open Robotics Foundation and dozens of OEMs.

---

## 🎯 Decision Matrix: When to Use DORA vs Keep ROS2

| Component | Recommendation | Rationale |
|-----------|---------------|-----------|
| **Camera pipeline** | ✅ DORA | Image data benefits from zero-copy |
| **LiDAR pipeline** | ✅ DORA | PointCloud2 is where DORA wins most. NEVER bridge to ROS2. |
| **NPU inference** | ✅ DORA | Isolated nodes, fault tolerance, Python RKNNLite API |
| **Perception fusion** | ✅ DORA | Multi-destination data, 1→N subscribers, zero-copy |
| **Behavior planning** | ✅ DORA | Dynamic topology for A/B testing |
| **MPC trajectory planning** | ✅ DORA | ACADOS Python interface — no C++ node needed |
| **100Hz PID control** | ✅ DORA | Operator for latency, safety-isolate in dedicated runtime |
| **Vehicle CAN interface** | ⚠️ ROS2 bridge | Proven ROS2 CAN stack, bridge at boundary only |
| **AEB / FCW / MRM** | ✅ DORA (isolated) | Separate `dorapilot_safety.yml`, `restart_policy: never` |
| **Voice stack** | ❌ Keep ROS2 | Low bandwidth, no latency requirement |
| **Navigation / OSM** | ❌ Keep ROS2 | Nav2 ecosystem, no need to migrate |
| **Dashboard / UI** | ❌ Keep ROS2 | Qt5/ros2 bridge, non-critical |
| **BLE / NCP telemetry** | ❌ Keep ROS2 | Existing protocol implementation |

---

## Best Practices from dora-autoware (Real-Vehicle Ported Experience)

### Lesson 1: Python-First is the Intended Pattern
The dora-autoware port uses the **Python API** for the majority of nodes. NDT localization, object detection, planning — all Python. The Rust core handles IPC; application logic stays Python. This is not a workaround; it is the pattern.

### Lesson 2: Never Bridge PointCloud2
The dora-autoware team hit a **hard blocker**: PointCloud2 struct arrays panic the Arrow↔ROS2 converter. Their successful fix: keep LiDAR 100% DORA-native. Dorapilot adopts this rule as law.

### Lesson 3: Parse Raw Bytes with Numpy (No C++ Parser)
Instead of a C++ parsing node, use numpy byte parsing:
```python
data = event["value"].to_numpy().view(np.uint8)
points = np.frombuffer(data, dtype=np.float32).reshape(-1, 4)
```
This is C-speed (numpy-vectorized) and eliminates a C++ node entirely.

### Lesson 4: Separate Safety Dataflow
Autoware's safety modules run in an **independent dataflow**. A main pipeline restart does not affect AEB/MRM. Dorapilot uses `dorapilot_safety.yml` separate from `dorapilot_main.yml`.

### Lesson 5: Start Simple, Migrate Gradually
Dora-autoware did not port everything at once. They started with sensing → perception → planning, kept vehicle interface in ROS2, and bridged at the boundary. Dorapilot follows the same phased approach.

---

## 📊 Benchmark Summary (from arxiv 2602.13252v1)

**Test Platform:** AMD Ryzen 5 5600, 32GB RAM, Ubuntu 22.04, Linux 6.8  
**ROS2 Version:** Humble with FastDDS  
**DORA Version:** 1.0-era

### Local Transmission (same machine)

| Scenario | DORA | ROS2 | CyberRT | Winner |
|----------|------|------|---------|--------|
| 4MB @ 20Hz | **0.82 ms** | 17.1 ms | 12.9 ms | DORA (21×) |
| 4MB @ 50Hz | **0.78 ms** | 4.9 ms | 13.0 ms | DORA (6.3×) |
| 4MB @ 200Hz | **0.73 ms** | 4.9 ms | 146.6 ms | DORA (6.8×) |
| 32MB @ 50Hz | **2.78 ms** | 87.0 ms | 250.0 ms | DORA (31×) |
| 1→4 subscribers | **<1 ms** | 15.3 ms | 54.0 ms | DORA (15×+) |
| 4→1 fusion | **1–5 ms** | ~50 ms | ~50 ms | DORA (10–50×) |
| CPU utilization (deserialization) | **~0%** | >30% | >30% | DORA |

### LAN Transmission (gigabit)

| Payload | DORA | ROS2 | ROS1 |
|---------|------|------|------|
| 32KB | 2.2 ms | 0.9 ms | 7.3 ms | ROS2 (small data wins) |
| 1MB | **15 ms** | 120 ms | 1.5 s | DORA (8×) |
| 4MB | **81 ms** | 544 ms | 8.3 s | DORA (6.7×) |

**Insight:** For small data (<32KB) over network, ROS2 is actually slightly faster due to DDS efficiency. For ADAS payloads (images, pointclouds >1MB), DORA dominates.

### Real-World Robotics (Realman Gen72 arm + ACT model)

| Metric | DORA | ROS2 | Advantage |
|--------|------|------|-----------|
| Image latency (640×480) | **~1.5 ms** | ~22.0 ms | **14.7×** |
| Consistency | Very stable | Jittery | DORA |

---

## 🏁 Verdict

**DORA is the right choice for dorapilot IF:**
1. LiDAR + camera fusion is a core requirement (zero-copy is transformative)
2. Team is willing to invest in building custom nodes (we already do in VisionPilot)
3. Migration is gradual — ROS2 bridge for vehicle interface and non-critical modules
4. We accept the risk of a younger ecosystem in exchange for 10-30× IPC performance
5. We commit to **Python-only application code** — no C++ nodes, no CMake, no Rust required for daily development

**ROS2 would be safer IF:**
1. We needed off-the-shelf Nav2, MoveIt, or complex C++ libraries
2. Safety certification timeline is tight (no precedent for DORA)
3. LiDAR is not in the near-term roadmap (the main performance win vanishes)
4. We are not comfortable with a younger framework

**Recommended path for dorapilot:**
> **Hybrid architecture**: DORA-native for sensing + perception + planning + control (the data-heavy pipeline, all in Python). ROS2 bridge for vehicle actuation, voice, navigation, and dashboard. This gives us 90% of DORA's performance benefits with 10% of the migration risk. And we keep 100% Python — the language that made VisionPilot work.

---

## References

1. **arxiv 2602.13252v1** — "DORA: Dataflow Oriented Robotic Architecture" (Feb 2026). Rigorous benchmark vs ROS1/ROS2/CyberRT.
2. **github.com/dora-rs/dora-benchmark** — GPU-to-GPU and CPU benchmarks. ROS2 fails at 40MB.
3. **github.com/dora-rs/dora-autoware** — Autoware porting effort to DORA. Real vehicle deployment reported at GOSIM 2024.
4. **github.com/dora-rs/dora-drives** — CARLA-based autonomous driving tutorial with DORA.
5. **github.com/orgs/dora-rs/discussions/999** — Node Hub limitations analysis.
6. **github.com/dora-rs/dora-autoware/discussions/10** — PointCloud2 bridge panic issue.
7. **china2024.gosim.org** — "The Application of Dora in the Autonomous Driving" presentation (Oct 2024).
8. **arxiv 2503.02911v1** — Text2Scenario benchmark including Dora-RS as SUT.

---

*Document version 1.0 — 2026-05-30 — Python-Native Edition*
