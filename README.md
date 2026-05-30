# DoraPilot 🚗⚡

**Next-generation ADAS stack for ExoPilot 03+ — powered by dora-rs**

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![DORA](https://img.shields.io/badge/Middleware-dora--rs%201.0-orange.svg)]()
[![Platform](https://img.shields.io/badge/Platform-RK3688-green.svg)]()

DoraPilot is the successor to [VisionPilot](https://github.com/exo-electronics/visionpilot), re-architected on **dora-rs** (Dataflow-Oriented Robotic Architecture) for 10-31× faster IPC, zero-copy LiDAR fusion, and declarative pipeline definitions.

## Why DoraPilot?

VisionPilot proved ADAS on Rockchip NPUs. DoraPilot takes the next leap:

| | VisionPilot (ROS2) | **DoraPilot (DORA)** |
|---|---|---|
| **LiDAR IPC Latency** | 15-20ms (DDS serialization) | **<1ms** (Zenoh SHM zero-copy) |
| **Camera → Control Pipeline** | ~60ms end-to-end | **~46ms** end-to-end |
| **Pipeline Definition** | 150 packages, Python launch files | **~60 packages, declarative YAML** |
| **A/B Testing Models** | Restart entire system | **Live node add/remove** |
| **Record/Replay** | MCAP bags (no substitution) | **`.drec` + node substitution** |
| **Fault Tolerance** | External systemd watchdogs | **Built-in restart policies** |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    DORA DATAFLOW (Zero-Copy)                │
│  Camera ──► Perception ──► Planning ──► Control             │
│     │           │              │            │                │
│  LiDAR ◄───────┘              │            ▼                │
│                           Trajectory    Vehicle             │
│                           Selector      (ROS2 bridge)       │
└──────────────────────────────┬──────────────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │   ROS2 Boundary     │
                    │  CAN / Voice / Nav  │
                    └─────────────────────┘
```

- **DORA-native**: sensing, perception, planning, control
- **ROS2 bridge**: vehicle interface, voice, navigation, dashboard
- **Safety isolation**: AEB/FCW/MRM run in separate dataflow

## Hardware Targets

| Platform | SoC | NPU | Cameras | LiDAR | Status |
|----------|-----|-----|---------|-------|--------|
| **ExoPilot 03** | RK3688 | 12 TOPS | 5× + telephoto | Pandar QT64 | 🎯 Target |
| **ExoPilot 03H** | RK3688 | 12 TOPS + premium | 5× + driver cam | Pandar QT64 | 🎯 Target |
| **ExoPilot 04** | RKxxxx | TBD | TBD | TBD | 🔮 Future |

## Quick Start

### Prerequisites

- Ubuntu 22.04 LTS (ARM64)
- Python 3.11+
- Rust toolchain (for DORA CLI)
- RK3688 with NPU drivers (`rknpu2`)

### Install DORA

```bash
# Install DORA CLI
cargo install dora-cli

# Install Python API
pip install dora-rs numpy pyarrow

# Verify
dora --version
```

### Run Simulation

```bash
# Clone
git clone <repo> ~/dorapilot
cd ~/dorapilot

# Run main pipeline in dev mode
dora run dataflows/dorapilot_main.yml --verbose
```

### Run on Vehicle

```bash
# Start coordinator + daemon
dora up

# Start main ADAS pipeline
dora start dataflows/dorapilot_main.yml --name dorapilot_main --attach

# Start safety pipeline (isolated)
dora start dataflows/dorapilot_safety.yml --name dorapilot_safety --attach

# Monitor
dora top
```

## Documentation

- **[docs/research/DORA_MIGRATION_RESEARCH.md](docs/research/DORA_MIGRATION_RESEARCH.md)** — Full research: why DORA, benchmarks, migration strategy
- **[docs/research/DORA_PROS_CONS.md](docs/research/DORA_PROS_CONS.md)** — Detailed pros/cons, risk analysis, decision matrix
- **[docs/architecture/DORAPILOT_PROPOSED_ARCHITECTURE.md](docs/architecture/DORAPILOT_PROPOSED_ARCHITECTURE.md)** — Proposed v1.0 architecture, dataflow YAML, performance budgets

## Project Status

| Phase | Status | Description |
|-------|--------|-------------|
| Research | ✅ Complete | DORA evaluated, benchmarks validated, architecture drafted |
| Phase 1: Foundation | ⏳ Pending | Bootstrap DORA on RK3688, inference_daemon port |
| Phase 2: Perception | ⏳ Pending | Camera + LiDAR pipeline, NPU inference nodes |
| Phase 3: Planning/Control | ⏳ Pending | MPC trajectory planner, 100Hz PID controllers |
| Phase 4: Safety | ⏳ Pending | AEB/FCW/MRM in isolated dataflow |
| Phase 5: Integration | ⏳ Pending | ROS2 bridge, vehicle testing |

## Research Highlights

- **arxiv 2602.13252v1** (Feb 2026): Peer-reviewed benchmark showing DORA 21× faster than ROS2 for 4MB payloads
- **dora-autoware**: Active port of Autoware.universe to DORA with real-vehicle deployment
- **GOSIM China 2024**: Featured presentation on DORA in autonomous driving

## License

Apache 2.0 — See [LICENSE](LICENSE)

## Acknowledgments

- [VisionPilot](https://github.com/exo-electronics/visionpilot) — Proven ADAS foundation
- [dora-rs](https://github.com/dora-rs/dora) — Next-gen robotics middleware
- [OpenPilot](https://github.com/commaai/openpilot) — Core driving technology
- [Autoware](https://github.com/autowarefoundation/autoware) — Architecture patterns

---

**DoraPilot** — Smaller latency, cleaner architecture, safer driving.
