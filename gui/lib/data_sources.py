import json
import math
import random
from typing import Callable, Optional

from PyQt5.QtCore import QObject, QPointF, QTimer

from .models import DetectedObject, UiState


UiStateCallback = Callable[[UiState], None]


def compute_min_distance(scan_points: list[QPointF]) -> float:
    distances = []
    for point in scan_points:
        if abs(point.x()) < 2.5 and point.y() > 0.0:
            distances.append(math.hypot(point.x(), point.y()))
    return min(distances) if distances else 99.0


class DemoDataSource(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._callback: Optional[UiStateCallback] = None
        self._t = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._publish_next_state)

    def start(self, callback: UiStateCallback) -> None:
        self._callback = callback
        self._timer.start(100)

    def stop(self) -> None:
        self._timer.stop()

    def _generate_fake_scan(self) -> list[QPointF]:
        points = []
        angles_deg = range(-90, 91, 2)

        for ang_deg in angles_deg:
            ang = math.radians(ang_deg)
            dist = 12.0 + 1.2 * math.sin(self._t * 0.7 + ang * 2.0)

            if -12 <= ang_deg <= 8:
                dist = min(dist, 4.0 + 0.5 * math.sin(self._t * 2.0))
            if 25 <= ang_deg <= 38:
                dist = min(dist, 7.0 + 0.4 * math.cos(self._t * 1.5))
            if -40 <= ang_deg <= -30:
                dist = min(dist, 9.0 + 0.2 * math.sin(self._t * 1.3))

            dist += random.uniform(-0.08, 0.08)
            dist = max(0.5, min(20.0, dist))

            x = dist * math.sin(ang)
            y = dist * math.cos(ang)
            points.append(QPointF(x, y))

        return points

    def _generate_fake_lane(self) -> list[QPointF]:
        points = []
        for y in [m * 0.4 for m in range(4, 40)]:
            wobble = 0.12 * math.sin(self._t * 0.9 + y * 0.35)
            points.append(QPointF(-1.8 + wobble, y))
            points.append(QPointF(1.8 + wobble, y))
        return points

    def _generate_fake_objects(self) -> list[DetectedObject]:
        obstacle_a_x = 1.2 * math.sin(self._t * 0.8)
        obstacle_a_y = 5.5 + 0.4 * math.sin(self._t * 1.3)
        obstacle_b_x = -2.8 + 0.4 * math.cos(self._t * 0.6)
        obstacle_b_y = 10.0 + 0.3 * math.sin(self._t * 0.9)

        return [
            DetectedObject(x_m=obstacle_a_x, y_m=obstacle_a_y, kind="obstacle"),
            DetectedObject(x_m=obstacle_b_x, y_m=obstacle_b_y, kind="obstacle"),
        ]

    def _publish_next_state(self) -> None:
        if self._callback is None:
            return

        self._t += 0.1
        scan_points = self._generate_fake_scan()
        lane_points = self._generate_fake_lane()
        objects = self._generate_fake_objects()
        min_distance = compute_min_distance(scan_points)
        speed_kmh = 8.0 + 2.5 * math.sin(self._t * 0.7)
        obstacle_count = len(objects)

        self._callback(
            UiState(
                scan_points=scan_points,
                lane_points=lane_points,
                objects=objects,
                speed_kmh=speed_kmh,
                min_distance_m=min_distance,
                obstacle_count=obstacle_count,
                mode="AUTO",
                gps_status="FIX",
            )
        )


class Ros2DataSource(QObject):
    def __init__(
        self,
        *,
        scan_topic: str,
        lane_topic: str,
        objects_topic: str,
        speed_topic: str,
        mode_topic: str,
        gps_topic: str,
        parent=None,
    ):
        super().__init__(parent)
        self._callback: Optional[UiStateCallback] = None
        self._scan_topic = scan_topic
        self._lane_topic = lane_topic
        self._objects_topic = objects_topic
        self._speed_topic = speed_topic
        self._mode_topic = mode_topic
        self._gps_topic = gps_topic
        self._timer: Optional[QTimer] = None
        self._node = None
        self._rclpy = None
        self._scan_points: list[QPointF] = []
        self._lane_points: list[QPointF] = []
        self._objects: list[DetectedObject] = []
        self._speed_kmh = 0.0
        self._mode = "--"
        self._gps_status = "--"

    def start(self, callback: UiStateCallback) -> None:
        self._callback = callback

        try:
            import rclpy
            from rclpy.executors import SingleThreadedExecutor
            from sensor_msgs.msg import LaserScan
            from std_msgs.msg import Float32, String
        except ImportError as exc:
            raise RuntimeError(
                "ROS2 mode requires rclpy, sensor_msgs, and std_msgs to be available."
            ) from exc

        self._rclpy = rclpy
        if not rclpy.ok():
            rclpy.init(args=None)

        node = rclpy.create_node("robot_ui_gui")
        executor = SingleThreadedExecutor()
        executor.add_node(node)

        node.create_subscription(LaserScan, self._scan_topic, self._on_scan, 10)
        node.create_subscription(LaserScan, self._lane_topic, self._on_lane, 10)
        node.create_subscription(String, self._objects_topic, self._on_objects, 10)
        node.create_subscription(Float32, self._speed_topic, self._on_speed, 10)
        node.create_subscription(String, self._mode_topic, self._on_mode, 10)
        node.create_subscription(String, self._gps_topic, self._on_gps, 10)

        self._node = {"node": node, "executor": executor}
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._spin_once)
        self._timer.start(30)
        self._emit_state()

    def stop(self) -> None:
        if self._timer is not None:
            self._timer.stop()

        if not self._node or self._rclpy is None:
            return

        executor = self._node["executor"]
        node = self._node["node"]
        executor.remove_node(node)
        node.destroy_node()

        if self._rclpy.ok():
            self._rclpy.shutdown()

        self._node = None
        self._rclpy = None

    def _spin_once(self) -> None:
        if not self._node or self._rclpy is None:
            return
        self._node["executor"].spin_once(timeout_sec=0.0)

    def _emit_state(self) -> None:
        if self._callback is None:
            return

        self._callback(
            UiState(
                scan_points=self._scan_points,
                lane_points=self._lane_points,
                objects=self._objects,
                speed_kmh=self._speed_kmh,
                min_distance_m=compute_min_distance(self._scan_points),
                obstacle_count=len(self._objects),
                mode=self._mode,
                gps_status=self._gps_status,
            )
        )

    def _on_scan(self, msg) -> None:
        angle = msg.angle_min
        points = []
        for distance in msg.ranges:
            if math.isfinite(distance) and msg.range_min <= distance <= msg.range_max:
                x = distance * math.sin(angle)
                y = distance * math.cos(angle)
                points.append(QPointF(x, y))
            angle += msg.angle_increment
        self._scan_points = points
        self._emit_state()

    def _on_lane(self, msg) -> None:
        angle = msg.angle_min
        points = []
        for distance in msg.ranges:
            if math.isfinite(distance) and msg.range_min <= distance <= msg.range_max:
                x = distance * math.sin(angle)
                y = distance * math.cos(angle)
                points.append(QPointF(x, y))
            angle += msg.angle_increment
        self._lane_points = points
        self._emit_state()

    def _on_objects(self, msg) -> None:
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            return

        if not isinstance(payload, list):
            return

        objects = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            kind = str(item.get("kind", "unknown"))
            try:
                x_m = float(item["x_m"])
                y_m = float(item["y_m"])
            except (KeyError, TypeError, ValueError):
                continue
            objects.append(DetectedObject(x_m=x_m, y_m=y_m, kind=kind))

        self._objects = objects
        self._emit_state()

    def _on_speed(self, msg) -> None:
        self._speed_kmh = float(msg.data)
        self._emit_state()

    def _on_mode(self, msg) -> None:
        self._mode = msg.data
        self._emit_state()

    def _on_gps(self, msg) -> None:
        self._gps_status = msg.data
        self._emit_state()
