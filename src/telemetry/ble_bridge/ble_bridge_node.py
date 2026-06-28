#!/usr/bin/env python3
"""BLE bridge — NavPilot phone app ↔ DoraPilot via Bluetooth SPP/BLE.

Receives navigation commands and engagement requests from NavPilot.
Sends vehicle state, alerts, and nav status back to phone.

Inputs:   nav_status     (String JSON)
          vehicle_state  (VehicleState)
          dms_event      (String JSON)
Outputs:  ui_cmd         (String JSON — commands from phone)
"""
import json
import os
import threading
from dora import Node

from drp_msgs.std_msgs import String
from drp_msgs.vehicle_msgs import VehicleState
from drp_msgs.utils import to_arrow, from_arrow

BLE_DEVICE = os.environ.get("BLE_DEVICE", "hci0")
NAVPILOT_UUID = os.environ.get("NAVPILOT_UUID", "00001101-0000-1000-8000-00805F9B34FB")


class BleBridgeNode:
    def __init__(self):
        self.node = Node()
        self._ble_socket = None
        self._rx_thread = None
        self._pending_cmds: list[str] = []
        self._lock = threading.Lock()
        # BLE setup in background — don't block DORA startup
        threading.Thread(target=self._init_ble, daemon=True).start()

    def _init_ble(self):
        # TODO: implement BlueZ D-Bus or pybluez SPP/BLE GATT
        pass

    def run(self):
        for event in self.node:
            if event["type"] != "INPUT":
                if event["type"] == "STOP":
                    break
                continue

            # Forward phone commands to DORA pipeline
            with self._lock:
                for cmd in self._pending_cmds:
                    self.node.send_output("ui_cmd", to_arrow(String(data=cmd)))
                self._pending_cmds.clear()

            # Forward vehicle/nav state to phone
            if event["id"] == "vehicle_state":
                self._send_ble(event)
            elif event["id"] == "nav_status":
                self._send_ble(event)

    def _send_ble(self, event):
        if self._ble_socket is None:
            return
        try:
            data = from_arrow(event["value"], String).data if event["id"] == "nav_status" else "{}"
            self._ble_socket.send((json.dumps({"topic": event["id"], "data": data}) + "\n").encode())
        except Exception:
            self._ble_socket = None


if __name__ == "__main__":
    BleBridgeNode().run()
