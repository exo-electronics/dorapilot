#!/usr/bin/env python3
"""Intent dispatcher — routes structured intents to ADAS or UI command outputs.

Inputs:   intent       (String JSON from nlu)
          llm_response (String from llm)
Outputs:  adas_cmd     (String — ADAS action commands)
          ui_cmd       (String — UI/navigation/audio commands)
          tts_text     (String — text to speak back to driver)
"""
import json
from dora import Node

from drp_msgs.std_msgs import String
from drp_msgs.utils import to_arrow, from_arrow

ADAS_INTENTS = {"engage_adas", "disengage_adas"}
NAV_INTENTS = {"navigate_to", "cancel_navigation"}
AUDIO_INTENTS = {"volume_up", "volume_down"}


class IntentNode:
    def __init__(self):
        self.node = Node()

    def run(self):
        for event in self.node:
            if event["type"] != "INPUT":
                if event["type"] == "STOP":
                    break
                continue

            if event["id"] == "intent":
                self._on_intent(event)
            elif event["id"] == "llm_response":
                self._on_llm(event)

    def _on_intent(self, event):
        data = json.loads(from_arrow(event["value"], String).data)
        intent = data.get("intent", "unknown")
        slots = data.get("slots", {})

        if intent in ADAS_INTENTS:
            self.node.send_output("adas_cmd", to_arrow(String(data=json.dumps(data))))
            self.node.send_output("tts_text", to_arrow(String(data=self._ack(intent))))
        elif intent in NAV_INTENTS:
            self.node.send_output("ui_cmd", to_arrow(String(data=json.dumps(data))))
            self.node.send_output("tts_text", to_arrow(String(data=self._ack(intent, slots))))
        elif intent in AUDIO_INTENTS:
            self.node.send_output("ui_cmd", to_arrow(String(data=json.dumps(data))))

    def _on_llm(self, event):
        msg = from_arrow(event["value"], String)
        if msg.data:
            self.node.send_output("tts_text", to_arrow(msg))

    def _ack(self, intent: str, slots: dict | None = None) -> str:
        acks = {
            "engage_adas": "Autopilot engaged.",
            "disengage_adas": "Autopilot disengaged.",
            "navigate_to": f"Navigating to {slots.get('destination', 'destination')}.",
            "cancel_navigation": "Navigation cancelled.",
        }
        return acks.get(intent, "Done.")


if __name__ == "__main__":
    IntentNode().run()
