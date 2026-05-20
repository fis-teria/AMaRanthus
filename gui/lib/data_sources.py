import json
import math
import os
import random
import struct
import threading
import time
from typing import Callable, Optional

from PyQt5.QtCore import QPoint, QObject, QPointF, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QImage, QPainter, QPen, QPolygon

from .models import (
    CameraFrame,
    DetectedObject,
    GeoPoint,
    PointCloudPoint,
    RouteStep,
    ShadowMetrics,
    UiState,
)


UiStateCallback = Callable[[UiState], None]
LiveDataCallback = Callable[[str], None]
LogCallback = Callable[[str, str], None]


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

    def _generate_fake_pointcloud(self) -> list[PointCloudPoint]:
        points = []
        for y_index in range(-20, 81, 2):
            forward = y_index * 0.5
            for x_index in range(-20, 21, 2):
                lateral = x_index * 0.25
                if abs(lateral) < 1.1 and 0.0 < forward < 28.0:
                    continue
                road_crown = 0.03 * math.cos(lateral * 1.2)
                ripple = 0.04 * math.sin(self._t * 0.7 + forward * 0.35 + lateral * 0.8)
                points.append(
                    PointCloudPoint(x_m=forward, y_m=lateral, z_m=road_crown + ripple)
                )

        for angle_index in range(0, 360, 8):
            angle = math.radians(angle_index)
            radius = 0.9 + 0.12 * math.sin(angle * 3.0)
            points.append(
                PointCloudPoint(
                    x_m=8.0 + radius * math.sin(angle),
                    y_m=1.8 + radius * math.cos(angle),
                    z_m=0.9 + 0.25 * math.sin(angle),
                )
            )

        return points

    def _publish_next_state(self) -> None:
        if self._callback is None:
            return

        self._t += 0.1
        scan_points = self._generate_fake_scan()
        lane_points = self._generate_fake_lane()
        pointcloud_points = self._generate_fake_pointcloud()
        objects = self._generate_fake_objects()
        min_distance = compute_min_distance(scan_points)
        speed_kmh = 8.0 + 2.5 * math.sin(self._t * 0.7)
        obstacle_count = len(objects)
        ego_speed_mps = speed_kmh / 3.6
        ego_curvature = 0.025 * math.sin(self._t * 0.4)
        virtual_curvature = ego_curvature + 0.010 * math.sin(self._t * 1.1)
        driver_steering = math.atan(2.7 * ego_curvature)
        virtual_steering = math.atan(2.7 * virtual_curvature)
        steering_delta = virtual_steering - driver_steering
        curvature_delta = virtual_curvature - ego_curvature
        warning_score = min(1.0, max(0.0, 1.0 - min_distance / 12.0))
        intervention_score = min(
            1.0,
            abs(steering_delta) / 0.35
            + abs(curvature_delta) / 0.20
            + warning_score * 0.35,
        )

        self._callback(
            UiState(
                scan_points=scan_points,
                lane_points=lane_points,
                pointcloud_points=pointcloud_points,
                objects=objects,
                speed_kmh=speed_kmh,
                min_distance_m=min_distance,
                obstacle_count=obstacle_count,
                mode="AUTO",
                gps_status="FIX",
                shadow=ShadowMetrics(
                    ego_speed_mps=ego_speed_mps,
                    ego_yaw_rate_radps=ego_speed_mps * ego_curvature,
                    ego_curvature_inv_m=ego_curvature,
                    virtual_steering_rad=virtual_steering,
                    virtual_curvature_inv_m=virtual_curvature,
                    virtual_warning_score=warning_score,
                    driver_steering_proxy_rad=driver_steering,
                    steering_delta_rad=steering_delta,
                    curvature_delta_inv_m=curvature_delta,
                    intervention_score=intervention_score,
                    summary="demo shadow metrics",
                ),
                camera_frame=self._generate_fake_camera_frame(),
            )
        )

    def _generate_fake_camera_frame(self) -> CameraFrame:
        width = 960
        height = 540
        image = QImage(width, height, QImage.Format_RGB888)
        image.fill(QColor(34, 52, 76))
        painter = QPainter(image)
        horizon = int(height * 0.42)
        painter.fillRect(0, horizon, width, height - horizon, QColor(50, 54, 58))
        painter.setPen(QPen(QColor(220, 225, 225), 5))
        painter.drawLine(width // 2 - 55, height, width // 2 - 8, horizon + 16)
        painter.drawLine(width // 2 + 55, height, width // 2 + 8, horizon + 16)
        painter.setPen(QPen(QColor(255, 214, 80), 4))
        for offset in range(0, 180, 44):
            painter.drawLine(width // 2, height - offset, width // 2, height - offset - 24)
        painter.setBrush(QColor(25, 28, 32))
        painter.setPen(QPen(QColor(190, 205, 220), 2))
        car = QPolygon(
            [
                QPoint(width // 2 - 44, horizon + 78),
                QPoint(width // 2 + 44, horizon + 78),
                QPoint(width // 2 + 58, horizon + 120),
                QPoint(width // 2 - 58, horizon + 120),
            ]
        )
        painter.drawPolygon(car)
        painter.end()

        return CameraFrame(
            image=image,
            width=width,
            height=height,
            encoding="rgb8",
            frame_id="demo_front_camera",
            stamp_sec=self._t,
            topic="demo",
        )


class Ros2DataSource(QObject):
    _state_signal = pyqtSignal(object)
    _live_signal = pyqtSignal(str)
    _log_signal = pyqtSignal(str, str)

    def __init__(
        self,
        *,
        camera_image_topic: str,
        camera_overlay_topic: str,
        camera_compressed_overlay_topic: str,
        camera_overlay_timeout_sec: float,
        camera_raw_overlay_fallback: bool,
        camera_raw_fallback: bool,
        camera_display_max_edge_px: int,
        camera_info_topic: str,
        pointcloud_topic: str,
        pointcloud_max_points: int,
        pointcloud_min_update_interval_sec: float,
        pointcloud_max_range_m: float,
        pointcloud_z_min_m: float,
        pointcloud_z_max_m: float,
        scan_topic: str,
        lane_topic: str,
        objects_topic: str,
        speed_topic: str,
        mode_topic: str,
        gps_topic: str,
        phone_fix_topic: str,
        phone_goal_topic: str,
        phone_status_topic: str,
        shadow_ego_speed_topic: str,
        shadow_ego_yaw_rate_topic: str,
        shadow_ego_curvature_topic: str,
        shadow_virtual_steering_topic: str,
        shadow_virtual_curvature_topic: str,
        shadow_virtual_warning_topic: str,
        shadow_driver_steering_topic: str,
        shadow_steering_delta_topic: str,
        shadow_curvature_delta_topic: str,
        shadow_intervention_score_topic: str,
        shadow_summary_topic: str,
        parent=None,
    ):
        super().__init__(parent)
        self._callback: Optional[UiStateCallback] = None
        self._camera_image_topic = camera_image_topic
        self._camera_overlay_topic = camera_overlay_topic
        self._camera_compressed_overlay_topic = camera_compressed_overlay_topic
        self._camera_overlay_timeout_sec = max(0.0, float(camera_overlay_timeout_sec))
        self._camera_raw_overlay_fallback = bool(camera_raw_overlay_fallback)
        self._camera_raw_fallback = bool(camera_raw_fallback)
        self._camera_display_max_edge_px = max(0, int(camera_display_max_edge_px))
        self._camera_info_topic = camera_info_topic
        self._pointcloud_topic = pointcloud_topic
        self._pointcloud_max_points = max(100, int(pointcloud_max_points))
        self._pointcloud_min_update_interval_sec = max(
            0.0, float(pointcloud_min_update_interval_sec)
        )
        self._pointcloud_max_range_m = max(1.0, float(pointcloud_max_range_m))
        self._pointcloud_z_min_m = float(pointcloud_z_min_m)
        self._pointcloud_z_max_m = float(pointcloud_z_max_m)
        self._scan_topic = scan_topic
        self._lane_topic = lane_topic
        self._objects_topic = objects_topic
        self._speed_topic = speed_topic
        self._mode_topic = mode_topic
        self._gps_topic = gps_topic
        self._phone_fix_topic = phone_fix_topic
        self._phone_goal_topic = phone_goal_topic
        self._phone_status_topic = phone_status_topic
        self._shadow_ego_speed_topic = shadow_ego_speed_topic
        self._shadow_ego_yaw_rate_topic = shadow_ego_yaw_rate_topic
        self._shadow_ego_curvature_topic = shadow_ego_curvature_topic
        self._shadow_virtual_steering_topic = shadow_virtual_steering_topic
        self._shadow_virtual_curvature_topic = shadow_virtual_curvature_topic
        self._shadow_virtual_warning_topic = shadow_virtual_warning_topic
        self._shadow_driver_steering_topic = shadow_driver_steering_topic
        self._shadow_steering_delta_topic = shadow_steering_delta_topic
        self._shadow_curvature_delta_topic = shadow_curvature_delta_topic
        self._shadow_intervention_score_topic = shadow_intervention_score_topic
        self._shadow_summary_topic = shadow_summary_topic
        self._timer: Optional[QTimer] = None
        self._spin_thread: Optional[threading.Thread] = None
        self._pointcloud_thread: Optional[threading.Thread] = None
        self._stop_spin = threading.Event()
        self._stop_pointcloud = threading.Event()
        self._ros_spin_interval_ms = max(
            1, int(os.environ.get("ROS_SPIN_INTERVAL_MS", "5"))
        )
        self._ros_spin_max_callbacks = max(
            1, int(os.environ.get("ROS_SPIN_MAX_CALLBACKS", "8"))
        )
        self._ros_spin_budget_sec = max(
            0.001, float(os.environ.get("ROS_SPIN_BUDGET_SEC", "0.001"))
        )
        self._ui_min_emit_interval_sec = max(
            0.0, float(os.environ.get("ROS_UI_MIN_EMIT_INTERVAL_SEC", "0.05"))
        )
        self._last_ui_emit_at = 0.0
        self._node = None
        self._rclpy = None
        self._point_cloud2 = None
        self._live_callback: Optional[LiveDataCallback] = None
        self._log_callback: Optional[LogCallback] = None
        self._has_live_data = False
        self._live_fields: set[str] = set()
        self._pointcloud_messages = 0
        self._pointcloud_processed_messages = 0
        self._pointcloud_parse_errors = 0
        self._last_pointcloud_update_at = 0.0
        self._latest_pointcloud_msg = None
        self._latest_pointcloud_seq = 0
        self._processed_pointcloud_seq = 0
        self._pointcloud_view_enabled = False
        self._pointcloud_lock = threading.Lock()
        self._camera_messages = 0
        self._camera_parse_errors = 0
        self._camera_overlay_messages = 0
        self._camera_overlay_parse_errors = 0
        self._camera_overlay_received_at: Optional[float] = None
        self._camera_info_messages = 0
        self._camera_frame: Optional[CameraFrame] = None
        self._pointcloud_points: list[PointCloudPoint] = []
        self._scan_points: list[QPointF] = []
        self._lane_points: list[QPointF] = []
        self._objects: list[DetectedObject] = []
        self._speed_kmh = 0.0
        self._mode = "--"
        self._gps_status = "--"
        self._phone_current: Optional[GeoPoint] = None
        self._phone_goal: Optional[GeoPoint] = None
        self._phone_route_points: list[GeoPoint] = []
        self._phone_route_steps: list[RouteStep] = []
        self._shadow_metrics = ShadowMetrics()
        self._state_signal.connect(self._dispatch_state)
        self._live_signal.connect(self._dispatch_live_data)
        self._log_signal.connect(self._dispatch_log)

    def set_live_callback(self, callback: Optional[LiveDataCallback]) -> None:
        self._live_callback = callback

    def set_log_callback(self, callback: Optional[LogCallback]) -> None:
        self._log_callback = callback

    def set_pointcloud_view_enabled(self, enabled: bool) -> None:
        was_enabled = self._pointcloud_view_enabled
        self._pointcloud_view_enabled = bool(enabled)
        if self._pointcloud_view_enabled and not was_enabled:
            self._log("INFO", "PointCloud viewer parsing enabled")
        elif was_enabled and not self._pointcloud_view_enabled:
            self._log("INFO", "PointCloud viewer parsing paused")

    def start(self, callback: UiStateCallback) -> None:
        self._callback = callback

        try:
            import rclpy
            from rclpy.executors import SingleThreadedExecutor
            from rclpy.qos import (
                DurabilityPolicy,
                HistoryPolicy,
                QoSProfile,
                ReliabilityPolicy,
            )
            from sensor_msgs.msg import (
                CameraInfo,
                CompressedImage,
                Image,
                LaserScan,
                NavSatFix,
                PointCloud2,
            )
            from sensor_msgs_py import point_cloud2
            from std_msgs.msg import Float32, String
        except ImportError as exc:
            self._log(
                "ERROR",
                "ROS2 imports failed: rclpy, sensor_msgs, sensor_msgs_py, std_msgs, and numpy are required.",
            )
            raise RuntimeError(
                "ROS2 mode requires rclpy, sensor_msgs, sensor_msgs_py, and std_msgs to be available."
            ) from exc

        self._log("INFO", "ROS2 data source starting.")
        self._rclpy = rclpy
        if not rclpy.ok():
            rclpy.init(args=None)

        node = rclpy.create_node("robot_ui_gui")
        executor = SingleThreadedExecutor()
        executor.add_node(node)

        self._point_cloud2 = point_cloud2
        best_effort_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=5,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        camera_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        pointcloud_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        if self._camera_raw_fallback and self._camera_image_topic:
            node.create_subscription(
                Image,
                self._camera_image_topic,
                self._on_camera_image,
                camera_qos,
            )
        if self._camera_compressed_overlay_topic:
            node.create_subscription(
                CompressedImage,
                self._camera_compressed_overlay_topic,
                self._on_camera_compressed_overlay_image,
                camera_qos,
            )
        if self._camera_raw_overlay_fallback or not self._camera_compressed_overlay_topic:
            node.create_subscription(
                Image,
                self._camera_overlay_topic,
                self._on_camera_overlay_image,
                camera_qos,
            )
        node.create_subscription(
            CameraInfo,
            self._camera_info_topic,
            self._on_camera_info,
            best_effort_qos,
        )
        node.create_subscription(
            PointCloud2,
            self._pointcloud_topic,
            self._on_pointcloud,
            pointcloud_qos,
        )
        node.create_subscription(LaserScan, self._scan_topic, self._on_scan, 10)
        node.create_subscription(LaserScan, self._lane_topic, self._on_lane, 10)
        node.create_subscription(String, self._objects_topic, self._on_objects, 10)
        node.create_subscription(Float32, self._speed_topic, self._on_speed, 10)
        node.create_subscription(String, self._mode_topic, self._on_mode, 10)
        node.create_subscription(String, self._gps_topic, self._on_gps, 10)
        node.create_subscription(NavSatFix, self._phone_fix_topic, self._on_phone_fix, 10)
        node.create_subscription(String, self._phone_goal_topic, self._on_phone_goal, 10)
        node.create_subscription(String, self._phone_status_topic, self._on_phone_status, 10)
        node.create_subscription(
            Float32,
            self._shadow_ego_speed_topic,
            self._shadow_float_callback("ego_speed_mps"),
            10,
        )
        node.create_subscription(
            Float32,
            self._shadow_ego_yaw_rate_topic,
            self._shadow_float_callback("ego_yaw_rate_radps"),
            10,
        )
        node.create_subscription(
            Float32,
            self._shadow_ego_curvature_topic,
            self._shadow_float_callback("ego_curvature_inv_m"),
            10,
        )
        node.create_subscription(
            Float32,
            self._shadow_virtual_steering_topic,
            self._shadow_float_callback("virtual_steering_rad"),
            10,
        )
        node.create_subscription(
            Float32,
            self._shadow_virtual_curvature_topic,
            self._shadow_float_callback("virtual_curvature_inv_m"),
            10,
        )
        node.create_subscription(
            Float32,
            self._shadow_virtual_warning_topic,
            self._shadow_float_callback("virtual_warning_score"),
            10,
        )
        node.create_subscription(
            Float32,
            self._shadow_driver_steering_topic,
            self._shadow_float_callback("driver_steering_proxy_rad"),
            10,
        )
        node.create_subscription(
            Float32,
            self._shadow_steering_delta_topic,
            self._shadow_float_callback("steering_delta_rad"),
            10,
        )
        node.create_subscription(
            Float32,
            self._shadow_curvature_delta_topic,
            self._shadow_float_callback("curvature_delta_inv_m"),
            10,
        )
        node.create_subscription(
            Float32,
            self._shadow_intervention_score_topic,
            self._shadow_float_callback("intervention_score"),
            10,
        )
        node.create_subscription(String, self._shadow_summary_topic, self._on_shadow_summary, 10)

        self._node = {"node": node, "executor": executor}
        self._stop_spin.clear()
        self._spin_thread = threading.Thread(
            target=self._spin_loop,
            name="amaranthus-ros2-gui-spin",
            daemon=True,
        )
        self._spin_thread.start()
        self._stop_pointcloud.clear()
        self._pointcloud_thread = threading.Thread(
            target=self._pointcloud_loop,
            name="amaranthus-ros2-gui-pointcloud",
            daemon=True,
        )
        self._pointcloud_thread.start()
        if self._camera_raw_fallback and self._camera_image_topic:
            self._log("INFO", f"Subscribed camera image topic: {self._camera_image_topic}")
        else:
            self._log("INFO", "Raw camera image fallback subscription disabled")
        if self._camera_compressed_overlay_topic:
            self._log(
                "INFO",
                f"Subscribed compressed camera overlay topic: {self._camera_compressed_overlay_topic}",
            )
        if self._camera_raw_overlay_fallback or not self._camera_compressed_overlay_topic:
            self._log(
                "INFO",
                (
                    "Subscribed camera overlay topic: "
                    f"{self._camera_overlay_topic} "
                    f"(preferred for {self._camera_overlay_timeout_sec:.1f}s)"
                ),
            )
        else:
            self._log("INFO", "Raw camera overlay fallback subscription disabled")
        self._log("INFO", f"Subscribed camera info topic: {self._camera_info_topic}")
        self._log("INFO", f"Subscribed PointCloud2 topic: {self._pointcloud_topic}")
        self._log("INFO", f"Subscribed LaserScan topics: {self._scan_topic}, {self._lane_topic}")
        self._log(
            "INFO",
            (
                "Subscribed phone location topics: "
                f"{self._phone_fix_topic}, {self._phone_goal_topic}, {self._phone_status_topic}"
            ),
        )
        self._emit_state(force=True)

    def stop(self) -> None:
        if self._timer is not None:
            self._timer.stop()
        self._stop_spin.set()
        self._stop_pointcloud.set()
        if self._spin_thread is not None and self._spin_thread.is_alive():
            self._spin_thread.join(timeout=1.0)
        self._spin_thread = None
        if self._pointcloud_thread is not None and self._pointcloud_thread.is_alive():
            self._pointcloud_thread.join(timeout=1.0)
        self._pointcloud_thread = None

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

    def _spin_loop(self) -> None:
        while not self._stop_spin.is_set():
            if not self._node or self._rclpy is None:
                return
            if not self._rclpy.ok():
                return
            try:
                self._node["executor"].spin_once(timeout_sec=self._ros_spin_budget_sec)
            except Exception as exc:
                if self._stop_spin.is_set() or self._rclpy is None or not self._rclpy.ok():
                    return
                self._log("ERROR", f"ROS2 spin failed: {type(exc).__name__}: {exc}")

    def _pointcloud_loop(self) -> None:
        while not self._stop_pointcloud.is_set():
            wait_sec = self._pointcloud_min_update_interval_sec
            if wait_sec <= 0.0:
                wait_sec = 0.05
            if self._stop_pointcloud.wait(wait_sec):
                return
            if not self._pointcloud_view_enabled:
                continue

            now = time.monotonic()
            if (
                self._last_pointcloud_update_at > 0.0
                and now - self._last_pointcloud_update_at
                < self._pointcloud_min_update_interval_sec
            ):
                continue

            with self._pointcloud_lock:
                msg = self._latest_pointcloud_msg
                seq = self._latest_pointcloud_seq
            if msg is None or seq == self._processed_pointcloud_seq:
                continue

            self._process_pointcloud_message(msg, seq, now)

    def _spin_once(self) -> None:
        if not self._node or self._rclpy is None:
            return
        if not self._rclpy.ok():
            if self._timer is not None:
                self._timer.stop()
            return
        try:
            deadline = time.monotonic() + self._ros_spin_budget_sec
            for _ in range(self._ros_spin_max_callbacks):
                self._node["executor"].spin_once(timeout_sec=0.0)
                if time.monotonic() >= deadline:
                    break
        except Exception as exc:
            if self._rclpy is not None and not self._rclpy.ok():
                if self._timer is not None:
                    self._timer.stop()
                return
            self._log("ERROR", f"ROS2 spin failed: {type(exc).__name__}: {exc}")

    def _emit_state(self, *, force: bool = False) -> None:
        if self._callback is None:
            return
        now = time.monotonic()
        if (
            not force
            and self._ui_min_emit_interval_sec > 0.0
            and now - self._last_ui_emit_at < self._ui_min_emit_interval_sec
        ):
            return
        self._last_ui_emit_at = now

        self._state_signal.emit(
            UiState(
                scan_points=self._scan_points,
                lane_points=self._lane_points,
                pointcloud_points=self._pointcloud_points,
                objects=self._objects,
                speed_kmh=self._speed_kmh,
                min_distance_m=compute_min_distance(self._scan_points),
                obstacle_count=len(self._objects),
                mode=self._mode,
                gps_status=self._gps_status,
                shadow=self._shadow_metrics,
                camera_frame=self._camera_frame,
                phone_current=self._phone_current,
                phone_goal=self._phone_goal,
                phone_route_points=self._phone_route_points,
                phone_route_steps=self._phone_route_steps,
            )
        )

    def _mark_live_data(self, field_name: str) -> None:
        self._has_live_data = True
        if field_name not in self._live_fields:
            self._live_fields.add(field_name)
            self._log("INFO", f"ROS2 topic became live: {field_name}")
        if self._live_callback is not None:
            self._live_signal.emit(field_name)

    def _dispatch_state(self, state: UiState) -> None:
        if self._callback is not None:
            self._callback(state)

    def _dispatch_live_data(self, field_name: str) -> None:
        if self._live_callback is not None:
            self._live_callback(field_name)

    def _dispatch_log(self, level: str, message: str) -> None:
        if self._log_callback is not None:
            self._log_callback(level, message)
        else:
            print(f"[{level}] {message}")

    def _on_scan(self, msg) -> None:
        self._mark_live_data("scan")
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
        self._mark_live_data("lane")
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

    def _on_pointcloud(self, msg) -> None:
        self._mark_live_data("pointcloud")
        self._pointcloud_messages += 1

        with self._pointcloud_lock:
            self._latest_pointcloud_msg = msg
            self._latest_pointcloud_seq += 1

        if self._pointcloud_messages == 1:
            fields = ", ".join(getattr(field, "name", "?") for field in getattr(msg, "fields", []))
            self._log(
                "INFO",
                (
                    "PointCloud2 first frame: "
                    f"{getattr(msg, 'width', 0)}x{getattr(msg, 'height', 0)}, "
                    f"point_step={getattr(msg, 'point_step', '?')}, "
                    f"row_step={getattr(msg, 'row_step', '?')}, "
                    f"fields=[{fields}]"
                ),
            )

    def _process_pointcloud_message(self, msg, seq: int, now: float) -> None:
        max_points = self._pointcloud_max_points
        total_points = int(getattr(msg, "width", 0)) * max(1, int(getattr(msg, "height", 1)))
        stride = max(1, math.ceil(total_points / max_points))

        try:
            points = self._sample_pointcloud(msg, stride=stride, max_points=max_points)
        except Exception as exc:
            self._pointcloud_parse_errors += 1
            self._log(
                "ERROR",
                f"PointCloud2 parse failed ({self._pointcloud_parse_errors}): {type(exc).__name__}: {exc}",
            )
            points = []

        with self._pointcloud_lock:
            self._pointcloud_points = points
            self._processed_pointcloud_seq = seq
        self._last_pointcloud_update_at = now
        self._pointcloud_processed_messages += 1
        if (
            self._pointcloud_processed_messages == 1
            or self._pointcloud_processed_messages % 100 == 0
        ):
            self._log(
                "INFO",
                (
                    f"PointCloud2 parsed frame {self._pointcloud_processed_messages}: "
                    f"kept {len(points)} points, stride={stride}, max_points={max_points}"
                ),
            )
        self._emit_state()

    def _sample_pointcloud(self, msg, *, stride: int, max_points: int) -> list[PointCloudPoint]:
        points = self._sample_pointcloud_direct(msg, stride=stride, max_points=max_points)
        if points is not None:
            return points

        sampled = []
        cloud_iter = self._point_cloud2.read_points(
            msg,
            field_names=("x", "y", "z"),
            skip_nans=True,
        )
        for index, point in enumerate(cloud_iter):
            if index % stride != 0:
                continue
            x_m, y_m, z_m = self._extract_xyz(point)
            if self._pointcloud_point_is_visible(x_m, y_m, z_m):
                sampled.append(PointCloudPoint(x_m=x_m, y_m=y_m, z_m=z_m))
            if len(sampled) >= max_points:
                break
        return sampled

    def _sample_pointcloud_direct(
        self,
        msg,
        *,
        stride: int,
        max_points: int,
    ) -> Optional[list[PointCloudPoint]]:
        field_map = {field.name: field for field in getattr(msg, "fields", [])}
        xyz_fields = [field_map.get(name) for name in ("x", "y", "z")]
        if any(field is None for field in xyz_fields):
            return None

        endian = ">" if getattr(msg, "is_bigendian", False) else "<"
        unpackers = []
        for field in xyz_fields:
            fmt = self._point_field_struct_format(field.datatype)
            if fmt is None:
                return None
            unpackers.append((field.offset, struct.Struct(endian + fmt)))

        point_step = int(getattr(msg, "point_step", 0))
        if point_step <= 0:
            return None

        data = memoryview(msg.data)
        width = int(getattr(msg, "width", 0))
        height = max(1, int(getattr(msg, "height", 1)))
        row_step = int(getattr(msg, "row_step", 0))
        if width <= 0 or row_step <= 0:
            return None
        total_points = width * height
        sampled = []
        for point_index in range(0, total_points, stride):
            row_index = point_index // width
            column_index = point_index % width
            base_offset = row_index * row_step + column_index * point_step
            try:
                x_m = float(unpackers[0][1].unpack_from(data, base_offset + unpackers[0][0])[0])
                y_m = float(unpackers[1][1].unpack_from(data, base_offset + unpackers[1][0])[0])
                z_m = float(unpackers[2][1].unpack_from(data, base_offset + unpackers[2][0])[0])
            except (struct.error, ValueError):
                continue
            if self._pointcloud_point_is_visible(x_m, y_m, z_m):
                sampled.append(PointCloudPoint(x_m=x_m, y_m=y_m, z_m=z_m))
            if len(sampled) >= max_points:
                break
        return sampled

    def _point_field_struct_format(self, datatype: int) -> Optional[str]:
        return {
            1: "b",
            2: "B",
            3: "h",
            4: "H",
            5: "i",
            6: "I",
            7: "f",
            8: "d",
        }.get(int(datatype))

    def _pointcloud_point_is_visible(
        self,
        x_m: Optional[float],
        y_m: Optional[float],
        z_m: Optional[float],
    ) -> bool:
        if (
            x_m is None
            or y_m is None
            or z_m is None
            or not all(math.isfinite(v) for v in (x_m, y_m, z_m))
        ):
            return False
        if z_m < self._pointcloud_z_min_m or z_m > self._pointcloud_z_max_m:
            return False
        return math.hypot(x_m, y_m) <= self._pointcloud_max_range_m

    def _extract_xyz(self, point) -> tuple[Optional[float], Optional[float], Optional[float]]:
        try:
            if hasattr(point, "dtype") and getattr(point.dtype, "names", None):
                return float(point["x"]), float(point["y"]), float(point["z"])
            return float(point[0]), float(point[1]), float(point[2])
        except (IndexError, KeyError, TypeError, ValueError):
            return None, None, None

    def _log(self, level: str, message: str) -> None:
        self._log_signal.emit(level, message)

    def _on_camera_image(self, msg) -> None:
        self._mark_live_data("camera")
        self._camera_messages += 1
        if self._camera_overlay_is_fresh():
            return
        self._store_camera_frame(
            msg,
            topic=self._camera_image_topic,
            count=self._camera_messages,
            source_label="Camera",
            is_overlay=False,
        )

    def _on_camera_overlay_image(self, msg) -> None:
        self._mark_live_data("camera")
        self._camera_overlay_messages += 1
        self._store_camera_frame(
            msg,
            topic=self._camera_overlay_topic,
            count=self._camera_overlay_messages,
            source_label="Camera overlay",
            is_overlay=True,
        )

    def _on_camera_compressed_overlay_image(self, msg) -> None:
        self._mark_live_data("camera")
        self._camera_overlay_messages += 1
        self._store_compressed_camera_frame(
            msg,
            topic=self._camera_compressed_overlay_topic,
            count=self._camera_overlay_messages,
            source_label="Camera overlay compressed",
        )

    def _camera_overlay_is_fresh(self) -> bool:
        if self._camera_overlay_received_at is None:
            return False
        age_sec = time.monotonic() - self._camera_overlay_received_at
        return age_sec <= self._camera_overlay_timeout_sec

    def _store_camera_frame(
        self,
        msg,
        *,
        topic: str,
        count: int,
        source_label: str,
        is_overlay: bool,
    ) -> None:
        try:
            image = self._image_msg_to_qimage(msg)
        except Exception as exc:
            if is_overlay:
                self._camera_overlay_parse_errors += 1
                parse_errors = self._camera_overlay_parse_errors
            else:
                self._camera_parse_errors += 1
                parse_errors = self._camera_parse_errors
            self._log(
                "ERROR",
                f"{source_label} image parse failed ({parse_errors}): {type(exc).__name__}: {exc}",
            )
            return

        image = self._scale_camera_image(image)
        stamp = getattr(msg.header, "stamp", None)
        stamp_sec = 0.0
        if stamp is not None:
            stamp_sec = float(getattr(stamp, "sec", 0)) + float(getattr(stamp, "nanosec", 0)) * 1e-9
        self._camera_frame = CameraFrame(
            image=image,
            width=int(image.width()),
            height=int(image.height()),
            encoding=str(msg.encoding),
            frame_id=str(getattr(msg.header, "frame_id", "")),
            stamp_sec=stamp_sec,
            topic=topic,
        )
        if is_overlay:
            self._camera_overlay_received_at = time.monotonic()
        if count == 1 or count % 100 == 0:
            self._log(
                "INFO",
                (
                    f"{source_label} frame {count}: "
                    f"{msg.width}x{msg.height}->{image.width()}x{image.height()} "
                    f"encoding={msg.encoding} step={msg.step}"
                ),
            )
        self._emit_state()

    def _store_compressed_camera_frame(
        self,
        msg,
        *,
        topic: str,
        count: int,
        source_label: str,
    ) -> None:
        try:
            image = QImage.fromData(bytes(msg.data))
            if image.isNull():
                raise ValueError(f"unsupported compressed image format: {msg.format}")
        except Exception as exc:
            self._camera_overlay_parse_errors += 1
            self._log(
                "ERROR",
                (
                    f"{source_label} parse failed "
                    f"({self._camera_overlay_parse_errors}): {type(exc).__name__}: {exc}"
                ),
            )
            return

        image = self._scale_camera_image(image)
        stamp = getattr(msg.header, "stamp", None)
        stamp_sec = 0.0
        if stamp is not None:
            stamp_sec = float(getattr(stamp, "sec", 0)) + float(getattr(stamp, "nanosec", 0)) * 1e-9
        self._camera_frame = CameraFrame(
            image=image,
            width=int(image.width()),
            height=int(image.height()),
            encoding=f"compressed:{msg.format}",
            frame_id=str(getattr(msg.header, "frame_id", "")),
            stamp_sec=stamp_sec,
            topic=topic,
        )
        self._camera_overlay_received_at = time.monotonic()
        if count == 1 or count % 100 == 0:
            self._log(
                "INFO",
                (
                    f"{source_label} frame {count}: "
                    f"{image.width()}x{image.height()} encoding={msg.format} "
                    f"bytes={len(msg.data)}"
                ),
            )
        self._emit_state()

    def _scale_camera_image(self, image: QImage) -> QImage:
        if self._camera_display_max_edge_px <= 0:
            return image
        longest_edge = max(image.width(), image.height())
        if longest_edge <= self._camera_display_max_edge_px:
            return image
        return image.scaled(
            self._camera_display_max_edge_px,
            self._camera_display_max_edge_px,
            Qt.KeepAspectRatio,
            Qt.FastTransformation,
        )

    def _on_camera_info(self, msg) -> None:
        self._camera_info_messages += 1
        if self._camera_info_messages == 1:
            self._log("INFO", f"CameraInfo first frame: {msg.width}x{msg.height}")

    def _image_msg_to_qimage(self, msg) -> QImage:
        width = int(msg.width)
        height = int(msg.height)
        step = int(msg.step)
        encoding = str(msg.encoding).lower()
        payload = bytes(msg.data)

        if width <= 0 or height <= 0 or step <= 0:
            raise ValueError(f"invalid image shape {width}x{height} step={step}")

        if encoding in ("rgb8", "8uc3"):
            return QImage(payload, width, height, step, QImage.Format_RGB888).copy()
        if encoding == "bgr8":
            return QImage(payload, width, height, step, QImage.Format_BGR888).copy()
        if encoding == "rgba8":
            return QImage(payload, width, height, step, QImage.Format_RGBA8888).copy()
        if encoding == "bgra8":
            return QImage(payload, width, height, step, QImage.Format_ARGB32).copy()
        if encoding in ("yuv422", "uyvy"):
            return self._yuv422_to_qimage(payload, width, height, step, "uyvy")
        if encoding in ("yuv422_yuy2", "yuyv", "yuy2"):
            return self._yuv422_to_qimage(payload, width, height, step, "yuyv")
        if encoding in (
            "mono8",
            "8uc1",
            "bayer_rggb8",
            "bayer_bggr8",
            "bayer_gbrg8",
            "bayer_grbg8",
        ):
            return QImage(payload, width, height, step, QImage.Format_Grayscale8).copy()
        if encoding in ("mono16", "16uc1"):
            grayscale = self._mono16_to_mono8(payload, width, height, step, bool(msg.is_bigendian))
            return QImage(grayscale, width, height, width, QImage.Format_Grayscale8).copy()

        raise ValueError(f"unsupported encoding: {msg.encoding}")

    def _yuv422_to_qimage(self, payload: bytes, width: int, height: int, step: int, layout: str) -> QImage:
        try:
            import cv2
            import numpy as np
        except ImportError as exc:
            raise ValueError("yuv422 camera frames require cv2 and numpy") from exc

        raw = np.frombuffer(payload, dtype=np.uint8).reshape(height, step)
        yuv = raw[:, : width * 2].reshape(height, width, 2)
        code = cv2.COLOR_YUV2RGB_UYVY if layout == "uyvy" else cv2.COLOR_YUV2RGB_YUY2
        rgb = cv2.cvtColor(yuv, code)
        rgb = np.ascontiguousarray(rgb)
        return QImage(rgb.data, width, height, width * 3, QImage.Format_RGB888).copy()

    def _mono16_to_mono8(
        self,
        payload: bytes,
        width: int,
        height: int,
        step: int,
        is_bigendian: bool,
    ) -> bytes:
        output = bytearray(width * height)
        byte_index = 0 if is_bigendian else 1
        for y in range(height):
            row_start = y * step
            for x in range(width):
                source_index = row_start + x * 2 + byte_index
                if source_index < len(payload):
                    output[y * width + x] = payload[source_index]
        return bytes(output)

    def _on_objects(self, msg) -> None:
        self._mark_live_data("objects")
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
        self._mark_live_data("speed")
        self._speed_kmh = float(msg.data)
        self._emit_state()

    def _on_mode(self, msg) -> None:
        self._mark_live_data("mode")
        self._mode = msg.data
        self._emit_state()

    def _on_gps(self, msg) -> None:
        self._mark_live_data("gps")
        self._gps_status = msg.data
        self._emit_state()

    def _on_phone_fix(self, msg) -> None:
        if not math.isfinite(msg.latitude) or not math.isfinite(msg.longitude):
            return
        self._mark_live_data("gps")
        accuracy_m = None
        try:
            covariance = list(msg.position_covariance)
            if len(covariance) >= 1 and math.isfinite(covariance[0]) and covariance[0] > 0.0:
                accuracy_m = math.sqrt(covariance[0])
        except (TypeError, ValueError):
            accuracy_m = None
        self._phone_current = GeoPoint(
            lat=float(msg.latitude),
            lon=float(msg.longitude),
            name="phone",
            accuracy_m=accuracy_m,
        )
        self._emit_state()

    def _on_phone_goal(self, msg) -> None:
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            return
        goal = payload.get("goal") if isinstance(payload, dict) else None
        if not isinstance(goal, dict):
            return
        try:
            lat = float(goal["lat"])
            lon = float(goal["lon"])
        except (KeyError, TypeError, ValueError):
            return
        if not math.isfinite(lat) or not math.isfinite(lon):
            return
        self._mark_live_data("gps")
        self._phone_goal = GeoPoint(
            lat=lat,
            lon=lon,
            name=str(goal.get("name") or "goal"),
            accuracy_m=None,
        )
        self._emit_state()

    def _on_phone_status(self, msg) -> None:
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            return
        if not isinstance(payload, dict):
            return
        selected_route = payload.get("selected_route")
        geometry = selected_route.get("geometry") if isinstance(selected_route, dict) else None
        if not isinstance(geometry, list):
            if self._phone_route_points:
                self._phone_route_points = []
                self._phone_route_steps = []
                self._emit_state()
            return

        points: list[GeoPoint] = []
        for item in geometry:
            if not isinstance(item, dict):
                continue
            try:
                lat = float(item["lat"])
                lon = float(item["lon"])
            except (KeyError, TypeError, ValueError):
                continue
            if math.isfinite(lat) and math.isfinite(lon):
                points.append(GeoPoint(lat=lat, lon=lon, name="route"))
        self._mark_live_data("gps")
        self._phone_route_points = points
        self._phone_route_steps = self._parse_phone_route_steps(selected_route)
        self._emit_state()

    def _parse_phone_route_steps(self, selected_route: dict) -> list[RouteStep]:
        raw_steps = selected_route.get("guidance_steps")
        if not isinstance(raw_steps, list):
            return []
        steps: list[RouteStep] = []
        for item in raw_steps:
            if not isinstance(item, dict):
                continue
            try:
                lat = float(item["lat"])
                lon = float(item["lon"])
                route_index = int(item.get("route_index", 0))
                distance_m = float(item.get("distance_m", 0.0))
                duration_sec = float(item.get("duration_sec", 0.0))
            except (KeyError, TypeError, ValueError):
                continue
            if not math.isfinite(lat) or not math.isfinite(lon):
                continue
            steps.append(
                RouteStep(
                    lat=lat,
                    lon=lon,
                    route_index=max(0, route_index),
                    text=str(item.get("text") or "道なりに進む"),
                    distance_m=distance_m if math.isfinite(distance_m) else 0.0,
                    duration_sec=duration_sec if math.isfinite(duration_sec) else 0.0,
                )
            )
        return steps

    def _shadow_float_callback(self, field_name: str):
        def callback(msg) -> None:
            self._mark_live_data("shadow")
            setattr(self._shadow_metrics, field_name, float(msg.data))
            self._emit_state()

        return callback

    def _on_shadow_summary(self, msg) -> None:
        self._mark_live_data("shadow")
        self._shadow_metrics.summary = msg.data
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            self._emit_state()
            return

        if isinstance(payload, dict):
            summary_fields = {
                "ego_speed_mps": "ego_speed_mps",
                "ego_curvature_inv_m": "ego_curvature_inv_m",
                "driver_steering_proxy_rad": "driver_steering_proxy_rad",
                "virtual_steering_rad": "virtual_steering_rad",
                "steering_delta_rad": "steering_delta_rad",
                "virtual_curvature_inv_m": "virtual_curvature_inv_m",
                "curvature_delta_inv_m": "curvature_delta_inv_m",
                "virtual_warning_score": "virtual_warning_score",
                "intervention_score": "intervention_score",
            }
            for json_key, field_name in summary_fields.items():
                if json_key not in payload:
                    continue
                try:
                    setattr(self._shadow_metrics, field_name, float(payload[json_key]))
                except (TypeError, ValueError):
                    continue

        self._emit_state()
