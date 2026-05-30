# drp_msgs — Dorapilot Message Definitions

Pure-Python message types modeled after Autoware/ROS2 conventions. No IDL. No CMake. No rosidl.

## For Autoware Developers

If you know ROS2 messages, you already know drp_msgs. Same names, same fields, same patterns.

```python
from drp_msgs import Header, PointCloud2, PoseStamped, PerceptionContext
from drp_msgs.utils import to_arrow, from_arrow

# Create message (identical API to ROS2)
msg = PerceptionContext(
    header=Header(frame_id="base_link"),
    engagement=True,
    lead=LeadVehicle(distance_m=45.2, velocity_mps=15.0)
)

# Send through DORA (zero-copy Arrow)
node.send_output("context", to_arrow(msg))

# Receive from DORA
event = node.next()
ctx = from_arrow(event["value"], PerceptionContext)
print(ctx.lead.distance_m)  # 45.2

# Bridge to ROS2 (when needed)
ros2_dict = msg.to_dict()
publisher.publish(pa.array([ros2_dict]))
```

## Message Hierarchy

```
drp_msgs/
├── std_msgs.py       # Header, Time, String, Bool, Float32/64, Int32/64, UInt32/64
├── geometry_msgs.py  # Point, Quaternion, Pose, PoseStamped, Twist, Vector3, Transform
├── sensor_msgs.py    # Image, PointCloud2, PointField, Imu, NavSatFix
├── nav_msgs.py       # Path, Odometry
├── perception_msgs.py # PerceptionContext, DetectedObject, LeadVehicle, LaneLine, TrafficLight
├── planning_msgs.py  # Trajectory, TrajectoryPoint, ManeuverCommand
├── control_msgs.py   # LateralCommand, LongitudinalCommand
├── vehicle_msgs.py   # VehicleState, VehicleCommand, GearShift
├── safety_msgs.py    # EmergencyBrakeRequest, FCWEvent, MRMManeuver
└── utils.py          # to_arrow(), from_arrow(), to_ros2_msg(), from_ros2_msg()
```

## Why Not ROS2 .msg Files?

| ROS2 .msg | drp_msgs (Python) |
|-----------|-------------------|
| Requires `rosidl` + CMake + package.xml | Pure Python, zero compilation |
| IDL compilation step | Import and use immediately |
| C++ header generation | Not needed (Python-only stack) |
| Static types only | Full Python type hints + runtime validation |
| No autocomplete in editors | Full IDE autocomplete |

## Why Not Raw Python Dicts?

| Raw `dict` | drp_msgs dataclass |
|------------|-------------------|
| `data["engagemnt"]` → silent KeyError | `msg.engagement` → autocomplete + typo catching |
| No field documentation | Docstrings on every field |
| No unit conventions | Enforced suffixes (`_m`, `_mps`, `_rad`) |
| Schema drift between nodes | Single source of truth in `src/drp_msgs/` |

## Adding a New Message

1. Add dataclass to appropriate module (e.g., `perception_msgs.py`)
2. Include `to_dict()` and `from_dict()` methods
3. Export from `__init__.py`
4. Use `to_arrow()` / `from_arrow()` for DORA serialization
