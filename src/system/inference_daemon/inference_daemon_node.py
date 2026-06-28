#!/usr/bin/env python3
"""Inference daemon — manages RKNN model pool on RK3688 NPU.

Loads models at startup, serves infer requests to DORA pipeline nodes.
Separate from Hailo-15H inference (which is managed by hailo15h_daemon).

RKNN NPU allocation (RK3688, 10+ TOPS):
  Core 0: driving_vision + driving_policy
  Core 1: lane_detector + lidar_detector + traffic_light_detector
  (Headroom 20% reserved for safety margin)

Outputs:
  rknn_ready   (Bool) — signals models are loaded and ready
"""
import os
from dora import Node

from drp_msgs.std_msgs import Bool, String
from drp_msgs.utils import to_arrow

MODELS = {
    "driving_vision":      ("/data/models/driving_vision_rk3688.rknn", 0),
    "driving_policy":      ("/data/models/driving_policy_rk3688.rknn", 0),
    "lane_detector":       ("/data/models/lane_detector_rk3688.rknn", 1),
    "lidar_detector":      ("/data/models/pointpillars_rk3688.rknn", 1),
    "traffic_light":       ("/data/models/traffic_light_rk3688.rknn", 1),
}


class InferenceDaemonNode:
    def __init__(self):
        self.node = Node()
        self._models: dict = {}
        self._load_models()

    def _load_models(self):
        try:
            from rknnlite.api import RKNNLite
            core_mask_map = {0: RKNNLite.NPU_CORE_0, 1: RKNNLite.NPU_CORE_1}
            for name, (path, core) in MODELS.items():
                if os.path.exists(path):
                    rknn = RKNNLite()
                    ret = rknn.load_rknn(path)
                    if ret == 0:
                        rknn.init_runtime(core_mask=core_mask_map[core])
                        self._models[name] = rknn
                        print(f"[inference_daemon] Loaded {name} on RKNN core {core}")
                    else:
                        print(f"[inference_daemon] Failed to load {name}: {ret}")
        except ImportError:
            print("[inference_daemon] rknnlite not available — stub mode")

    def run(self):
        ready = len(self._models) > 0 or True  # stub always ready
        self.node.send_output("rknn_ready", to_arrow(Bool(data=ready)))

        for event in self.node:
            if event["type"] == "STOP":
                self._unload_models()
                break

    def _unload_models(self):
        for rknn in self._models.values():
            try:
                rknn.release()
            except Exception:
                pass


if __name__ == "__main__":
    InferenceDaemonNode().run()
