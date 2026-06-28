#!/usr/bin/env python3
"""NLU — classify intent + extract slots from STT text.

Routes to LLM (Hailo-10H) for complex queries, rule-based for simple commands.

Inputs:   stt_text  (String)
Outputs:  intent    (String — JSON: {intent, slots, route})
"""
import json
import re
from dora import Node

from drp_msgs.std_msgs import String
from drp_msgs.utils import to_arrow, from_arrow

SIMPLE_RULES: list[tuple[str, str, dict]] = [
    (r"\b(navigate|go)\b.*(home|work|office)", "navigate_to", {"destination": "home"}),
    (r"\b(cancel|stop)\b.*(navigation|route)", "cancel_navigation", {}),
    (r"\bautomatic\b|\bauto\b.*\b(on|enable)", "engage_adas", {}),
    (r"\bmanual\b|\bdisable\b|\boff\b", "disengage_adas", {}),
    (r"\b(volume|sound)\b.*(up|louder|increase)", "volume_up", {}),
    (r"\b(volume|sound)\b.*(down|quieter|decrease)", "volume_down", {}),
]


class NluNode:
    def __init__(self):
        self.node = Node()

    def run(self):
        for event in self.node:
            if event["type"] == "INPUT" and event["id"] == "stt_text":
                self._on_text(event)
            elif event["type"] == "STOP":
                break

    def _on_text(self, event):
        msg = from_arrow(event["value"], String)
        text = msg.data.lower().strip()

        result = self._match_rules(text)
        if result:
            route = "direct"
        else:
            result = {"intent": "unknown", "slots": {}, "raw": text}
            route = "llm"

        result["route"] = route
        payload = String(data=json.dumps(result))
        self.node.send_output("intent", to_arrow(payload))

    def _match_rules(self, text: str) -> dict | None:
        for pattern, intent, slots in SIMPLE_RULES:
            if re.search(pattern, text):
                return {"intent": intent, "slots": slots, "raw": text}
        return None


if __name__ == "__main__":
    NluNode().run()
