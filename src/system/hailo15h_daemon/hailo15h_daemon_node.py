#!/usr/bin/env python3
"""Hailo-15H daemon — GMSL2 camera hub + unified AI inference manager.

ExoPilot 03H dual-path camera architecture:
  PATH A — CSI-2 D-PHY direct → RK3688 (5 cameras, handled by camera_node.py):
    CSI0: road camera      (OX03C10, HDR4 140dB)
    CSI1: wide_road        (OX03C10, HDR4 140dB)
    CSI2: telephoto        (OX03C10, HDR4 140dB)
    CSI3: stereo_left      (GC4653, DWDR 110dB)
    CSI4: stereo_right     (GC4653, DWDR 110dB)

  PATH B — GMSL2 → Hailo-15H → RK3688 (4 cameras, this daemon):
    GMSL0: side_left       (automotive, up to 15m cable)
    GMSL1: side_right      (automotive)
    GMSL2: rear            (automotive, wide FOV)
    GMSL3: driver (DMS)    (NIR global shutter, in-cabin)

Hailo-15H replaces VisionPilot's USB UVC hub (RTS5411S) with automotive-grade
GMSL2 links + on-chip AI (BSD YOLO, DMS, Whisper STT, LLM).

Hailo-15H specs: combines Hailo-8 (vision AI) + Hailo-10H (LLM) capabilities.
  - Vision AI: BSD, DMS, face_pose, scene classification
  - LLM/STT: Whisper STT, small NLU, on-device voice reasoning
  - Interface: M.2 Key-M PCIe Gen3 x4 → RK3688

GMSL2 cameras connected:

This daemon:
  1. Initializes Hailo-15H hardware via HailoRT
  2. Loads vision HEF models (BSD, DMS, scene)
  3. Captures frames via GMSL2 V4L2 or Hailo camera API
  4. Runs inference, publishes detection outputs to DORA pipeline

Outputs:
  image_road          — main driving camera frame (Arrow bytes)
  image_wide          — wide angle frame
  image_stereo_left   — stereo left
  image_stereo_right  — stereo right
  hailo_detections    — BSD/object detections (Arrow list of dicts)
  hailo_dms_output    — DMS face pose (Arrow dict)
  hailo_scene_class   — scene classification
"""
import os
import time
from dora import Node
import pyarrow as pa
import numpy as np

from drp_msgs.sensor_msgs import Image
from drp_msgs.utils import to_arrow

HAILO_DEVICE = os.environ.get("HAILO_DEVICE", "/dev/hailo0")
BSD_HEF = os.environ.get("BSD_HEF", "/data/models/yolov8s_bsd_hailo15h.hef")
DMS_HEF = os.environ.get("DMS_HEF", "/data/models/face_pose_monitor_hailo15h.hef")
SCENE_HEF = os.environ.get("SCENE_HEF", "/data/models/scene_classifier_hailo15h.hef")
GMSL_CAMERAS = int(os.environ.get("GMSL_CAMERAS", "4"))  # side_L, side_R, rear, driver


class Hailo15HDaemonNode:
    def __init__(self):
        self.node = Node()
        self._hw = self._init_hailo()
        self._cameras = self._init_gmsl_cameras()
        self._bsd_net = self._load_hef(BSD_HEF, "bsd")
        self._dms_net = self._load_hef(DMS_HEF, "dms")

    def _init_hailo(self):
        """Initialize Hailo-15H VDevice via HailoRT."""
        try:
            from hailo_platform import VDevice
            params = VDevice.create_params()
            vdevice = VDevice(params)
            print(f"[hailo15h] Initialized Hailo-15H: {vdevice}")
            return vdevice
        except Exception as e:
            print(f"[hailo15h] Hardware not available ({e}) — running in stub mode")
            return None

    def _init_gmsl_cameras(self) -> list:
        """Open GMSL2 camera devices via V4L2 after Hailo-15H deserializer."""
        cameras = []
        for i in range(GMSL_CAMERAS):
            dev = f"/dev/video{i}"
            if os.path.exists(dev):
                try:
                    import cv2
                    cap = cv2.VideoCapture(dev)
                    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"NV12"))
                    cameras.append(cap)
                except Exception:
                    cameras.append(None)
            else:
                cameras.append(None)
        return cameras

    def _load_hef(self, hef_path: str, name: str):
        """Load a HEF model onto Hailo-15H."""
        if self._hw is None:
            return None
        try:
            from hailo_platform import HEF, ConfigureParams, HailoStreamInterface
            hef = HEF(hef_path)
            params = ConfigureParams.create_from_hef(hef, interface=HailoStreamInterface.PCIe)
            ngs = self._hw.configure(hef, params)
            print(f"[hailo15h] Loaded {name} HEF: {hef_path}")
            return ngs[0] if ngs else None
        except Exception as e:
            print(f"[hailo15h] Failed to load {name} HEF: {e}")
            return None

    def run(self):
        for event in self.node:
            if event["type"] == "INPUT" and event["id"] == "tick":
                self._capture_and_infer()
            elif event["type"] == "STOP":
                self._cleanup()
                break

    def _capture_and_infer(self):
        frames = self._grab_frames()

        # Publish GMSL2 camera frames (side/rear/driver) — CSI-2 cameras handled by camera_node.py
        cam_names = ["image_side_left", "image_side_right", "image_rear", "image_driver"]
        for i, (name, frame) in enumerate(zip(cam_names, frames)):
            if frame is not None:
                h, w = frame.shape[:2]
                img = Image(
                    width=w, height=h,
                    encoding="nv12",
                    data=frame.tobytes(),
                )
                self.node.send_output(name, to_arrow(img))

        # Run BSD on side_left + side_right + rear frames (indices 0, 1, 2)
        for cam_idx, cam_label in [(0, "side_left"), (1, "side_right"), (2, "rear")]:
            if cam_idx < len(frames) and frames[cam_idx] is not None and self._bsd_net is not None:
                detections = self._run_hef_infer(self._bsd_net, frames[cam_idx], "bsd")
                if detections:
                    if isinstance(detections, list):
                        for d in detections:
                            d["camera"] = cam_label
                    self.node.send_output("hailo_detections", pa.array(detections if isinstance(detections, list) else [detections]))

        # Run DMS on driver camera frame (index 3 = GMSL3)
        if len(frames) > 3 and frames[3] is not None and self._dms_net is not None:
            dms_out = self._run_hef_infer(self._dms_net, frames[3], "dms")
            if dms_out:
                self.node.send_output("hailo_dms_output", pa.array([dms_out]))

    def _grab_frames(self) -> list:
        frames = []
        for cap in self._cameras:
            if cap is not None:
                ret, frame = cap.read()
                frames.append(frame if ret else None)
            else:
                frames.append(None)
        return frames

    def _run_hef_infer(self, network_group, frame: np.ndarray, model_type: str):
        """Run HEF inference on a frame."""
        try:
            from hailo_platform import InferVStreams, InputVStreamParams, OutputVStreamParams
            input_params = InputVStreamParams.make_from_network_group(network_group, quantized=False)
            output_params = OutputVStreamParams.make_from_network_group(network_group, quantized=False)
            with network_group.activate():
                with InferVStreams(network_group, input_params, output_params) as pipeline:
                    inp_name = list(input_params.keys())[0]
                    frame_resized = self._resize_for_model(frame, inp_name)
                    result = pipeline.infer({inp_name: frame_resized[np.newaxis]})
                    return self._parse_output(result, model_type)
        except Exception:
            return None

    def _resize_for_model(self, frame: np.ndarray, inp_name: str) -> np.ndarray:
        # Most Hailo YOLO models expect 640×640
        try:
            import cv2
            return cv2.resize(frame, (640, 640))
        except Exception:
            return frame[:640, :640] if frame.shape[0] >= 640 else frame

    def _parse_output(self, result: dict, model_type: str):
        # TODO: parse specific output tensors per model
        return result

    def _cleanup(self):
        for cap in self._cameras:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass


if __name__ == "__main__":
    Hailo15HDaemonNode().run()
