#!/usr/bin/env python3
"""On-device LLM via Hailo-15H or CPU fallback — handles complex voice queries.

Hailo-15H: 20 TOPS vision AI processor (M.2 PCIe).
LLM support via small ONNX/HEF models (≤1B params recommended at 20 TOPS).
For larger LLMs (1.5B+), falls back to RK3688 RKNN NPU or CPU.

Inputs:   intent   (String JSON — route=="llm" messages only)
          perception_context (PerceptionContext — scene grounding)
Outputs:  llm_response (String)
"""
import json
import os
from dora import Node

from drp_msgs.std_msgs import String
from drp_msgs.perception_msgs import PerceptionContext
from drp_msgs.utils import to_arrow, from_arrow

LLM_MODEL = os.environ.get("LLM_MODEL", "llama32_1b")
LLM_DEVICE = os.environ.get("LLM_DEVICE", "hailo15h")  # or "rknn" or "cpu"
MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", "128"))

SYSTEM_PROMPT = (
    "You are Dora, the in-car AI assistant. "
    "Give brief, safe responses. "
    "Never distract the driver with long answers. "
    "Current scene context will be provided."
)


class LlmNode:
    def __init__(self):
        self.node = Node()
        self._context: PerceptionContext | None = None
        self._model = self._load_model()

    def _load_model(self):
        if LLM_DEVICE == "hailo15h":
            return self._load_hailo()
        if LLM_DEVICE == "rknn":
            return self._load_rknn()
        return None  # cpu stub mode

    def _load_hailo(self):
        try:
            # Hailo-15H: use HailoRT + HEF model (≤1B params for 20 TOPS budget)
            from hailo_platform import HEF, VDevice
            return {"type": "hailo15h", "hef_path": f"/data/models/{LLM_MODEL}.hef"}
        except ImportError:
            return None

    def _load_rknn(self):
        try:
            from rknnlite.api import RKNNLite
            rknn = RKNNLite()
            rknn.load_rknn(f"/data/models/{LLM_MODEL}_rk3688.rknn")
            rknn.init_runtime()
            return {"type": "rknn", "model": rknn}
        except Exception:
            return None

    def run(self):
        for event in self.node:
            if event["type"] != "INPUT":
                if event["type"] == "STOP":
                    break
                continue

            if event["id"] == "perception_context":
                self._context = from_arrow(event["value"], PerceptionContext)
            elif event["id"] == "intent":
                self._on_intent(event)

    def _on_intent(self, event):
        data = json.loads(from_arrow(event["value"], String).data)
        if data.get("route") != "llm":
            return

        query = data.get("raw", "")
        context_str = self._build_context_str()
        response = self._generate(query, context_str)
        self.node.send_output("llm_response", to_arrow(String(data=response)))

    def _build_context_str(self) -> str:
        if not self._context:
            return "No scene data available."
        ctx = self._context
        parts = []
        if ctx.lead:
            parts.append(f"Lead vehicle {ctx.lead.distance_m:.0f}m ahead at {ctx.lead.velocity_mps:.1f}m/s")
        parts.append(f"Engaged: {ctx.engagement}")
        return ". ".join(parts) or "Normal driving conditions."

    def _generate(self, query: str, context_str: str) -> str:
        if self._model is None:
            return f"[LLM stub] Query: {query}"

        prompt = f"{SYSTEM_PROMPT}\nScene: {context_str}\nDriver: {query}\nDora:"
        try:
            return self._model.generate(prompt).strip()
        except Exception as e:
            return ""


if __name__ == "__main__":
    LlmNode().run()
