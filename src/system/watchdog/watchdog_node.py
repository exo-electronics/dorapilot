#!/usr/bin/env python3
"""Watchdog — kicks hardware watchdog timer, triggers MRM on health failure.

Inputs:   health_status (from health_daemon)
          tick          (100ms interval)
Outputs:  watchdog_kick (Bool — True = kick)
          mrm_trigger   (String — triggers MRM handler on critical failure)
"""
import json
import time
import os
from dora import Node

from drp_msgs.std_msgs import String, Bool
from drp_msgs.utils import to_arrow, from_arrow

WATCHDOG_DEV = os.environ.get("WATCHDOG_DEV", "/dev/watchdog")
MAX_UNHEALTHY_S = float(os.environ.get("WATCHDOG_MAX_UNHEALTHY_S", "5.0"))


class WatchdogNode:
    def __init__(self):
        self.node = Node()
        self._unhealthy_since: float | None = None
        self._wd_fd = self._open_watchdog()

    def _open_watchdog(self):
        try:
            return open(WATCHDOG_DEV, "wb", buffering=0)
        except Exception:
            return None

    def run(self):
        for event in self.node:
            if event["type"] != "INPUT":
                if event["type"] == "STOP":
                    self._close_watchdog()
                    break
                continue

            if event["id"] == "tick":
                self._kick()
            elif event["id"] == "health_status":
                self._on_health(event)

    def _kick(self):
        if self._wd_fd:
            try:
                self._wd_fd.write(b"1")
            except Exception:
                pass
        self.node.send_output("watchdog_kick", to_arrow(Bool(data=True)))

    def _on_health(self, event):
        data = json.loads(from_arrow(event["value"], String).data)
        if data.get("healthy", True):
            self._unhealthy_since = None
            return

        now = time.time()
        if self._unhealthy_since is None:
            self._unhealthy_since = now
        elif now - self._unhealthy_since > MAX_UNHEALTHY_S:
            self.node.send_output("mrm_trigger", to_arrow(String(data=json.dumps({
                "reason": "health_daemon_critical",
                "stale_nodes": data.get("stale_nodes", []),
            }))))

    def _close_watchdog(self):
        if self._wd_fd:
            try:
                self._wd_fd.write(b"V")  # magic close
                self._wd_fd.close()
            except Exception:
                pass


if __name__ == "__main__":
    WatchdogNode().run()
