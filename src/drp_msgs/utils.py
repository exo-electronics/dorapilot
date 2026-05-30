"""
utils — Serialization and bridge helpers for drp_msgs

Converts between:
- Python dataclasses (drp_msgs)
- PyArrow arrays (DORA zero-copy IPC)
- JSON strings (human-readable, ROS2 bridge compatible)
- ROS2-compatible dicts (for dora-ros2-bridge)
"""

import json
from typing import Any, Type, TypeVar, Union
import pyarrow as pa
import numpy as np

T = TypeVar("T")


def _json_serialize(obj: Any) -> Any:
    """Recursively serialize numpy types for JSON."""
    if isinstance(obj, np.generic):
        return obj.item()
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, bytes):
        return obj.decode("latin-1")  # For image/pointcloud data
    elif isinstance(obj, dict):
        return {k: _json_serialize(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_json_serialize(v) for v in obj]
    return obj


def _json_deserialize(d: Any) -> Any:
    """Recursively deserialize JSON dicts (no-op for standard types)."""
    if isinstance(d, dict):
        return {k: _json_deserialize(v) for k, v in d.items()}
    elif isinstance(d, list):
        return [_json_deserialize(v) for v in d]
    return d


# ---------------------------------------------------------------------------
# Arrow serialization (for DORA zero-copy IPC)
# ---------------------------------------------------------------------------

def to_arrow(msg: Any) -> pa.Array:
    """Serialize any drp_msgs dataclass to PyArrow Array.

    This is the primary serialization path for DORA nodes.
    Data is serialized as JSON string inside a PyArrow array,
    which DORA passes via zero-copy shared memory.

    Example:
        from drp_msgs import PerceptionContext
        from drp_msgs.utils import to_arrow

        ctx = PerceptionContext(...)
        node.send_output("context", to_arrow(ctx))
    """
    if hasattr(msg, "to_dict"):
        d = msg.to_dict()
    elif isinstance(msg, dict):
        d = msg
    else:
        raise TypeError(f"Message must have to_dict() or be a dict, got {type(msg)}")

    json_str = json.dumps(_json_serialize(d), separators=(',', ':'))
    return pa.array([json_str])


def from_arrow(arr: pa.Array, msg_type: Type[T]) -> T:
    """Deserialize PyArrow Array back to drp_msgs dataclass.

    Example:
        from drp_msgs import PerceptionContext
        from drp_msgs.utils import from_arrow

        ctx = from_arrow(event["value"], PerceptionContext)
    """
    if len(arr) == 0:
        raise ValueError("Empty Arrow array")

    json_str = arr[0].as_py()
    d = json.loads(json_str)
    d = _json_deserialize(d)
    return msg_type.from_dict(d)


# ---------------------------------------------------------------------------
# Batch operations (for record/replay)
# ---------------------------------------------------------------------------

def to_arrow_batch(msgs: list, msg_type: Type[T] = None) -> pa.RecordBatch:
    """Serialize a batch of messages to Arrow RecordBatch.

    Useful for recording multiple frames to .drec files.
    """
    if not msgs:
        raise ValueError("Empty message list")

    json_strings = []
    for msg in msgs:
        if hasattr(msg, "to_dict"):
            d = msg.to_dict()
        elif isinstance(msg, dict):
            d = msg
        else:
            raise TypeError(f"Message must have to_dict() or be a dict, got {type(msg)}")
        json_strings.append(json.dumps(_json_serialize(d), separators=(',', ':')))

    return pa.record_batch([pa.array(json_strings)], names=["msg"])


def from_arrow_batch(batch: pa.RecordBatch, msg_type: Type[T]) -> list:
    """Deserialize Arrow RecordBatch back to list of drp_msgs dataclasses."""
    arr = batch.column("msg")
    return [msg_type.from_dict(json.loads(s.as_py())) for s in arr]


# ---------------------------------------------------------------------------
# ROS2 bridge helpers (for dora-ros2-bridge)
# ---------------------------------------------------------------------------

def to_ros2_msg(msg: Any) -> dict:
    """Convert drp_msgs dataclass to ROS2-compatible dict.

    The dora-ros2-bridge accepts dicts with ROS2 message structure
    and publishes them as actual ROS2 messages.

    Example:
        from drp_msgs import VehicleCommand
        from drp_msgs.utils import to_ros2_msg

        cmd = VehicleCommand(...)
        ros2_dict = to_ros2_msg(cmd)
        publisher.publish(pa.array([ros2_dict]))
    """
    if hasattr(msg, "to_dict"):
        return msg.to_dict()
    elif isinstance(msg, dict):
        return msg
    else:
        raise TypeError(f"Message must have to_dict() or be a dict, got {type(msg)}")


def from_ros2_msg(ros2_dict: dict, msg_type: Type[T]) -> T:
    """Convert ROS2-compatible dict to drp_msgs dataclass.

    Example:
        from drp_msgs import VehicleState
        from drp_msgs.utils import from_ros2_msg

        state = from_ros2_msg(ros2_dict, VehicleState)
    """
    return msg_type.from_dict(ros2_dict)


# ---------------------------------------------------------------------------
# Arrow schema inspection (for debugging)
# ---------------------------------------------------------------------------

def arrow_schema(msg_type: Type[T]) -> dict:
    """Return the JSON schema structure for a message type.

    Useful for debugging and documentation.
    """
    import inspect
    from dataclasses import fields

    def _field_type(f) -> str:
        t = f.type
        if hasattr(t, "__name__"):
            return t.__name__
        return str(t)

    result = {}
    for f in fields(msg_type):
        result[f.name] = _field_type(f)
    return result
