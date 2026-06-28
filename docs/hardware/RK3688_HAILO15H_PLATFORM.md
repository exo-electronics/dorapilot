# ExoPilot 03H Hardware Platform — RK3688 + Hailo-15H

**Date**: 2026-06-28  
**Status**: Design Phase  
**Board**: ExoPilot 03H  
**Software Stack**: DoraPilot (dora-rs)

---

## Platform Summary

| Component | Specification |
|-----------|---------------|
| **SoC** | Rockchip RK3688 |
| **CPU** | 8× Cortex-A76 @ 2.5GHz + 4× Cortex-A55 @ 2.0GHz |
| **RAM** | 16GB LPDDR4X |
| **NPU** | RKNN 10+ TOPS (built-in) |
| **GPU** | Mali-G720 MP4 |
| **Storage** | 64GB eMMC + NVMe SSD |
| **AI Accelerator** | Hailo-15H (M.2 PCIe Gen3 x4) |
| **CAN** | 2× CAN-FD (SocketCAN) |
| **LiDAR** | Hesai Pandar QT64 (10GbE) |

---

## Hailo-15H AI Accelerator

The Hailo-15H is the **unified AI accelerator** for ExoPilot 03H, combining capabilities
that previously required both Hailo-8 (vision AI) and Hailo-10H (LLM) on earlier platforms.

| Capability | Detail |
|------------|--------|
| **TOPS** | 20 TOPS (AI core) |
| **Interface** | M.2 Key-M, PCIe Gen3 x4 |
| **Power** | < 5W |
| **Vision AI** | BSD YOLO, DMS face_pose, scene classification |
| **Audio AI** | Whisper STT (HEF encoder) |
| **LLM** | ≤1B parameter models (Llama 3.2 1B, Qwen 2.5 1B) |
| **ISP** | 4K30 HDR, AI-ISP denoising < 0.01 LUX |
| **Camera inputs** | 2× MIPI CSI-2 (4-lane each) per chip |

**Comparison vs previous platforms:**

| Feature | ExoPilot 02M (RK3576) | ExoPilot 03H (RK3688) |
|---------|----------------------|----------------------|
| Vision AI accel | Hailo-8 (26 TOPS, M.2) | Hailo-15H (20 TOPS) |
| LLM support | ❌ No | ✅ Hailo-15H (≤1B) |
| Whisper STT | Hailo-8 HEF | Hailo-15H HEF |
| DMS | Hailo-8 HEF | Hailo-15H HEF |
| BSD | Hailo-8 HEF | Hailo-15H HEF |

---

## Camera Architecture — Dual-Path Design

ExoPilot 03H uses two separate camera input paths:

### PATH A — CSI-2 D-PHY Direct → RK3688 (5 cameras)
Main ADAS driving cameras, connected directly to RK3688 via MIPI CSI-2.
Processed by RK3688 RKNN NPU.

| Port | Camera | Sensor | Resolution | HDR |
|------|--------|--------|-----------|-----|
| CSI0 | road | OX03C10 | 1920×1280 | HDR4 140dB |
| CSI1 | wide_road | OX03C10 | 1920×1280 | HDR4 140dB |
| CSI2 | telephoto | OX03C10 | 1920×1280 | HDR4 140dB |
| CSI3 | stereo_left | GC4653 | 2560×1440 | DWDR 110dB |
| CSI4 | stereo_right | GC4653 | 2560×1440 | DWDR 110dB |

### PATH B — GMSL2 → Hailo-15H → RK3688 (4–6 side cameras)
Automotive-grade surround cameras (replacing VisionPilot's USB UVC hub).
Processed by Hailo-15H (BSD YOLO on-chip) before results reach RK3688.

| Port | Camera | Location | AI on Hailo-15H |
|------|--------|----------|-----------------|
| GMSL0 | side_front_left | A-pillar left | BSD YOLO |
| GMSL1 | side_front_right | A-pillar right | BSD YOLO |
| GMSL2 | side_rear_left | C-pillar left | BSD YOLO |
| GMSL3 | side_rear_right | C-pillar right | BSD YOLO |
| GMSL4 | rear_wide | Rear bumper | Object detection |
| GMSL5 | rear_tele | Rear bumper | Rear object |

### PATH C — USB → RK3688 (DMS camera)
Driver monitoring camera remains USB (continuity from VisionPilot).

| Interface | Camera | Sensor | Purpose |
|-----------|--------|--------|---------|
| USB 2.0/3.0 | driver | OV9282 (NIR GS) | DMS — face pose via Hailo-15H |

---

## CRITICAL: Hailo-15H GMSL2 Camera Limit

> **⚠️ Hardware constraint verified from SolidRun Hailo-15 SOM datasheet.**

The Hailo-15H chip has **2× MIPI CSI-2 inputs** per die — meaning each Hailo-15H
can directly connect to **maximum 2 cameras**.

For 6 GMSL2 side cameras (side_front_L/R, side_rear_L/R, rear_wide, rear_tele),
ExoPilot 03H requires one of these approaches:

### Option A — 3× Hailo-15H chips (Recommended for full AI)
```
side_front_L + side_front_R  → Hailo-15H #1 (BSD, 2 CSI-2)
side_rear_L  + side_rear_R   → Hailo-15H #2 (BSD, 2 CSI-2)
rear_wide    + rear_tele     → Hailo-15H #3 (object detect, 2 CSI-2)
```
Each chip connects via PCIe to RK3688. Requires 3× PCIe endpoints (PCIe switch or 3× slots).

### Option B — GMSL2 deserializer + Hailo-8 M.2 (Simpler hardware)
```
6× GMSL2 cameras → 2× MAX9296A deserializer (4 GMSL2 → 1 CSI-2 aggregated)
                 → RK3688 CSI or Hailo-8 M.2 for BSD AI
```
Lower AI performance (Hailo-8 26 TOPS shared across 6 cameras) but simpler board.

### Option C — GMSL2 deserializer + single Hailo-15H for 2-camera pairs
```
4× side cameras  → 2× GMSL2 deserializers → Hailo-15H (2 CSI inputs)
2× rear cameras  → separate CSI-2 → RK3688 direct (no Hailo AI on these)
```
Hybrid: Hailo-15H for side BSD, basic detection for rear.

**Current recommendation**: Confirm board design before DoraPilot software commit.

---

## RK3688 RKNN NPU Allocation

| Core | Node | TOPS Budget | Purpose |
|------|------|-------------|---------|
| Core 0 | driving_vision | 2.5 TOPS | End-to-end driving model |
| Core 0 | driving_policy | 0.5 TOPS | Neural path planning |
| Core 1 | lane_detector | 1.5 TOPS | Lane line detection |
| Core 1 | lidar_detector | 2.0 TOPS | PointPillars 3D detection |
| Core 1 | traffic_light_detector | 0.5 TOPS | Traffic light state |
| Reserved | — | 3.0 TOPS | 20% safety headroom |
| **Total used** | | **7.0 / 10+ TOPS** | **≤70%** |

---

## Hailo-15H AI Model Allocation

| HEF Model | TOPS | Input | Output |
|-----------|------|-------|--------|
| whisper_tiny_10s_encoder | 3.0 | mel spectrogram | logits → STT |
| yolov8s_bsd | 5.0 | side camera frame | BSD detections |
| face_pose_monitor | 2.0 | driver camera frame | pitch/yaw/roll |
| scene_classifier | 1.5 | road camera | scene class |
| llm_llama32_1b | 8.0 | text tokens | response tokens |
| **Total** | **19.5 / 20 TOPS** | | **97.5% — tight** |

> **Note**: LLM and Whisper STT are NOT run simultaneously.
> Model switching via HailoRT network group activation handles time-sharing.

---

## Comparison: VisionPilot USB vs DoraPilot GMSL2

| Aspect | VisionPilot (ExoPilot 02M) | DoraPilot (ExoPilot 03H) |
|--------|--------------------------|--------------------------|
| Side cameras | USB UVC via RTS5411S hub | GMSL2 automotive cameras |
| Cable length | USB: 5m max | GMSL2: up to 15m |
| AI on side cams | Hailo-8 PCIe (post-receive) | Hailo-15H (on-chip, pre-transmit) |
| BSD latency | Frame → USB → SoC → Hailo-8 | Frame → Hailo-15H local AI |
| DMS camera | USB UVC | USB (retained, V4L2) |
| Camera waterproofing | USB camera modules | Automotive GMSL2 grade |

---

## LiDAR Integration

| Component | Specification |
|-----------|---------------|
| Model | Hesai Pandar QT64 |
| Range | 200m @ 10% reflectivity |
| FOV | 360° horizontal, 104° vertical |
| Interface | Ethernet 1000BASE-T1 / PoE+ |
| Output | 64 channels, ~1.2M pts/sec @ 10Hz |
| DORA node | `sensing/lidar/lidar_node.py` |
| Processing | `sensing/operators/pointcloud_filter.py` → `perception/lidar_detector` |

---

## dora-rs Node to Hardware Mapping

| DORA Node | Hardware | Interface |
|-----------|----------|-----------|
| `hailo15h_daemon` | Hailo-15H (×1–3) | PCIe Gen3 x4 → /dev/hailo0 |
| `camera` | 5× OX03C10/GC4653 | CSI-2 D-PHY → /dev/video0–4 |
| `sensing/mic` | MEMS microphone array | ALSA hw:0,0 |
| `lidar` | Pandar QT64 | Ethernet 192.168.1.201 |
| `gnss` | u-blox ZED-F9P RTK | UART /dev/ttyUSB0 |
| `imu` | ICM-42688-P | I2C / SPI |
| `vehicle_bridge` | CAN-FD SocketCAN | can0 (500kbps) |
| `inference_daemon` | RK3688 RKNN NPU | /dev/rknpu |
| `whisper_stt` | Hailo-15H | /dev/hailo0 HEF |
| `llm` | Hailo-15H | /dev/hailo0 HEF |

---

## Software Stack

| Layer | Component |
|-------|-----------|
| OS | Ubuntu 24.04 LTS (ARM64) |
| Kernel | Linux 6.x Rockchip BSP |
| Middleware | dora-rs 1.0 (Zenoh SHM, Apache Arrow) |
| NPU runtime | rknnlite2 (RKNN NPU) + HailoRT (Hailo-15H) |
| Camera | V4L2 + Hailo ISP SDK |
| CAN | SocketCAN + custom DBC codec |
| Voice | Piper TTS + OpenWakeWord + Whisper HEF |

---

## Quick Start — ExoPilot 03H

```bash
# Check hardware
ls /dev/hailo*        # Hailo-15H PCIe devices
ls /dev/video*        # CSI-2 cameras (0-4) + DMS USB (5)
cat /proc/cpuinfo | grep "Hardware"

# Check Hailo-15H
hailortcli fw-control identify

# Run ADAS pipeline
cd ~/pilot/dorapilot
dora up
dora start dataflows/dorapilot_main.yml --name main --attach &
dora start dataflows/dorapilot_safety.yml --name safety --attach &
dora start dataflows/dorapilot_voice.yml --name voice --attach

# Monitor
dora top
```

---

*Status: Design phase — GMSL2 camera count (Option A/B/C) to be confirmed before PCB layout.*  
*See also: [exopilot/kernel/rk3688/README.md](../../../exopilot/kernel/rk3688/README.md)*
