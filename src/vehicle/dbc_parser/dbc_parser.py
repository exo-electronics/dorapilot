#!/usr/bin/env python3
"""DBC parser — loads vehicle .dbc file, encodes/decodes CAN messages.

Used by vehicle_bridge for CAN frame ↔ vehicle state translation.
"""
import struct
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Signal:
    name: str
    start_bit: int
    length: int
    factor: float = 1.0
    offset: float = 0.0
    min_val: float = 0.0
    max_val: float = 0.0
    unit: str = ""
    is_signed: bool = False


@dataclass
class Message:
    can_id: int
    name: str
    length: int
    signals: list[Signal] = field(default_factory=list)


class DbcParser:
    def __init__(self, dbc_path: str):
        self._messages: dict[int, Message] = {}
        self._load(dbc_path)

    def _load(self, path: str):
        if not Path(path).exists():
            return
        current_msg: Message | None = None
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("BO_ "):
                    parts = line.split()
                    can_id = int(parts[1])
                    name = parts[2].rstrip(":")
                    length = int(parts[3])
                    current_msg = Message(can_id=can_id, name=name, length=length)
                    self._messages[can_id] = current_msg
                elif line.startswith("SG_ ") and current_msg:
                    sig = self._parse_signal(line)
                    if sig:
                        current_msg.signals.append(sig)

    def _parse_signal(self, line: str) -> Signal | None:
        # SG_ SignalName : start_bit|length@byte_order value_type (factor,offset) [min|max] "unit"
        try:
            parts = line.split()
            name = parts[1]
            bit_info = parts[3]   # e.g. "8|8@1+"
            start_bit = int(bit_info.split("|")[0])
            rest = bit_info.split("|")[1]
            length = int(rest.split("@")[0])
            is_signed = "-" in rest
            factor_offset = parts[4].strip("()")
            factor = float(factor_offset.split(",")[0])
            offset = float(factor_offset.split(",")[1])
            return Signal(name=name, start_bit=start_bit, length=length,
                          factor=factor, offset=offset, is_signed=is_signed)
        except Exception:
            return None

    def decode(self, can_id: int, data: bytes) -> dict[str, float]:
        msg = self._messages.get(can_id)
        if not msg:
            return {}
        result = {}
        for sig in msg.signals:
            raw = self._extract_bits(data, sig.start_bit, sig.length, sig.is_signed)
            result[sig.name] = raw * sig.factor + sig.offset
        return result

    def encode(self, can_id: int, signals: dict[str, float]) -> bytes | None:
        msg = self._messages.get(can_id)
        if not msg:
            return None
        data = bytearray(msg.length)
        for sig in msg.signals:
            if sig.name in signals:
                raw = int((signals[sig.name] - sig.offset) / sig.factor)
                self._insert_bits(data, sig.start_bit, sig.length, raw)
        return bytes(data)

    def _extract_bits(self, data: bytes, start: int, length: int, signed: bool) -> int:
        value = int.from_bytes(data, byteorder="little")
        mask = (1 << length) - 1
        raw = (value >> start) & mask
        if signed and raw >= (1 << (length - 1)):
            raw -= (1 << length)
        return raw

    def _insert_bits(self, data: bytearray, start: int, length: int, value: int):
        mask = (1 << length) - 1
        value &= mask
        int_val = int.from_bytes(data, byteorder="little")
        int_val &= ~(mask << start)
        int_val |= (value << start)
        data[:] = int_val.to_bytes(len(data), byteorder="little")
