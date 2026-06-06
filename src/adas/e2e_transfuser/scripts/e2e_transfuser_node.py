#!/usr/bin/env python3
import json
import math
from pathlib import Path as FilePath
import sys

_SOURCE_ROOT = FilePath(__file__).resolve().parents[1]
if (_SOURCE_ROOT / "e2e_transfuser").exists():
    # symlink-install 時も source 側 helper package を import できるようにする。
    sys.path.insert(0, str(_SOURCE_ROOT))

import rclpy
from geometry_msgs.msg import PointStamped, PoseStamped
from nav_msgs.msg import Odometry, Path
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CameraInfo, Image, PointCloud2
from std_msgs.msg import Float32, String
from visualization_msgs.msg import Marker, MarkerArray

from e2e_transfuser.environment import inspect_lead_environment
from e2e_transfuser.lead_runtime import LeadTorchRuntime


def stamp_to_float(stamp):
    return float(stamp.sec) + float(stamp.nanosec) * 1.0e-9


def unique_topics(primary, fallback_topics):
    topics = [primary]
    if isinstance(fallback_topics, str):
        topics.append(fallback_topics)
    else:
        topics.extend(fallback_topics)
    unique = []
    for topic in topics:
        topic = str(topic)
        if topic and topic not in unique:
            unique.append(topic)
    return unique


def string_list(value):
    if value is None:
        return []
    values = value.split(",") if isinstance(value, str) else value
    result = []
    for item in values:
        text = str(item).strip()
        if text and text not in result:
            result.append(text)
    return result


class LatestSample:
    # 各入力 topic の最新値と受信時刻を持ち、stale 判定を共通化する。
    def __init__(self):
        self.msg = None
        self.received_at = None

    def update(self, msg, stamp):
        self.msg = msg
        self.received_at = stamp

    def age_sec(self, now):
        if self.received_at is None:
            return None
        return max(0.0, (now - self.received_at).nanoseconds * 1.0e-9)

    def fresh(self, now, timeout_sec):
        age = self.age_sec(now)
        return age is not None and age <= timeout_sec


class E2ETransfuserNode(Node):
    def __init__(self):
        super().__init__("e2e_transfuser")

        # LEAD runtime と軽量化設定。mock 以外は status に準備状態を出して node は落とさない。
        self.runtime_mode = self.declare_parameter("runtime_mode", "mock").value
        self.precision_mode = self.declare_parameter("precision_mode", "fp32").value
        self.model_variant = self.declare_parameter("model_variant", "tfv6_resnet34").value
        self.model_path = self.declare_parameter(
            "model_path", "Data/models/tfv6/tfv6_resnet34"
        ).value
        self.lead_project_root = self.declare_parameter("lead_project_root", "").value
        self.lead_python_site = self.declare_parameter("lead_python_site", "").value
        self.lead_torch_lib = self.declare_parameter("lead_torch_lib", "").value
        self.runtime_device = self.declare_parameter("runtime_device", "cuda:0").value
        self.input_preprocess_backend = self.declare_parameter(
            "input_preprocess_backend", "cpu"
        ).value
        self.lead_strict_weight_load = bool(
            self.declare_parameter("lead_strict_weight_load", False).value
        )
        self.lead_probe_on_startup = bool(
            self.declare_parameter("lead_probe_on_startup", True).value
        )
        self.lead_force_timm_pretrained_off = bool(
            self.declare_parameter("lead_force_timm_pretrained_off", True).value
        )
        self.lead_lidar_raster_enabled = bool(
            self.declare_parameter("lead_lidar_raster_enabled", True).value
        )
        self.lead_lidar_flip_y_axis = bool(
            self.declare_parameter("lead_lidar_flip_y_axis", True).value
        )
        self.lead_lidar_history_size = int(
            self.declare_parameter("lead_lidar_history_size", 1).value
        )
        self.lead_lidar_max_points = int(
            self.declare_parameter("lead_lidar_max_points", 250000).value
        )
        self.lead_lidar_expected_frame_ids = string_list(
            self.declare_parameter("lead_lidar_expected_frame_ids", "body,base_link").value
        )
        self.image_topic = self.declare_parameter(
            "image_topic", "/sensing/camera/camera0/image_rect_color"
        ).value
        self.image_fallback_topics = self.declare_parameter(
            "image_fallback_topics",
            ["/sensing/camera/camera0/image_rect_color", "/image_rect_color"],
        ).value
        if bool(self.declare_parameter("disable_image_fallback_topics", False).value):
            self.image_fallback_topics = []
        self.camera_info_topic = self.declare_parameter(
            "camera_info_topic", "/sensing/camera/camera0/camera_info"
        ).value
        self.synthesize_camera_info_when_missing = bool(
            self.declare_parameter("synthesize_camera_info_when_missing", False).value
        )
        self.synthetic_camera_info_focal_length_px = float(
            self.declare_parameter("synthetic_camera_info_focal_length_px", 0.0).value
        )
        self.synthetic_camera_info_frame_id = self.declare_parameter(
            "synthetic_camera_info_frame_id", ""
        ).value
        self.pointcloud_topic = self.declare_parameter("pointcloud_topic", "/livox/lidar").value
        self.sensor_input_mode = self.declare_parameter("sensor_input_mode", "auto").value
        self.odom_topic = self.declare_parameter("odom_topic", "/Odometry").value
        self.target_point_topic = self.declare_parameter(
            "target_point_topic", "/shadow/route/target_point"
        ).value
        self.target_path_topic = self.declare_parameter(
            "target_path_topic", "/shadow/route/target_path"
        ).value
        self.use_target_path_triplet = bool(
            self.declare_parameter("use_target_path_triplet", True).value
        )
        self.target_path_previous_distance_m = float(
            self.declare_parameter("target_path_previous_distance_m", 5.0).value
        )
        self.target_path_current_distance_m = float(
            self.declare_parameter("target_path_current_distance_m", 15.0).value
        )
        self.target_path_next_distance_m = float(
            self.declare_parameter("target_path_next_distance_m", 25.0).value
        )
        self.target_path_speed_adaptive = bool(
            self.declare_parameter("target_path_speed_adaptive", True).value
        )
        self.target_path_speed_lookahead_time_sec = max(
            0.0,
            float(self.declare_parameter("target_path_speed_lookahead_time_sec", 1.2).value),
        )
        self.target_path_max_current_distance_m = max(
            self.target_path_current_distance_m,
            float(self.declare_parameter("target_path_max_current_distance_m", 60.0).value),
        )
        self.target_path_min_forward_distance_m = float(
            self.declare_parameter("target_path_min_forward_distance_m", 0.5).value
        )
        self.target_path_expected_frame_ids = string_list(
            self.declare_parameter("target_path_expected_frame_ids", "base_link,body").value
        )
        self.target_path_require_expected_frame = bool(
            self.declare_parameter("target_path_require_expected_frame", True).value
        )
        self.route_command_topic = self.declare_parameter(
            "route_command_topic", "/shadow/route/command"
        ).value
        self.output_frame = self.declare_parameter("output_frame", "base_link").value
        self.raw_lead_path_topic = self.declare_parameter(
            "raw_lead_path_topic", "/shadow/e2e/path_raw_lead"
        ).value
        self.publish_rate_hz = float(self.declare_parameter("publish_rate_hz", 10.0).value)
        self.input_timeout_sec = float(self.declare_parameter("input_timeout_sec", 0.5).value)
        self.camera_only_confidence_scale = self.clamp01(
            float(self.declare_parameter("camera_only_confidence_scale", 0.75).value)
        )
        self.max_waypoints = int(self.declare_parameter("max_waypoints", 10).value)
        self.waypoint_spacing_m = float(self.declare_parameter("waypoint_spacing_m", 1.5).value)
        self.wheel_base_m = float(self.declare_parameter("wheel_base_m", 2.7).value)
        self.default_target_x_m = float(self.declare_parameter("default_target_x_m", 15.0).value)
        self.default_target_y_m = float(self.declare_parameter("default_target_y_m", 0.0).value)
        self.require_target_point = bool(
            self.declare_parameter("require_target_point", True).value
        )
        self.enable_debug_markers = bool(
            self.declare_parameter("enable_debug_markers", True).value
        )
        self.lead_flip_y_axis = bool(self.declare_parameter("lead_flip_y_axis", True).value)
        self.disable_aux_heads = bool(self.declare_parameter("disable_aux_heads", True).value)
        self.single_checkpoint = bool(self.declare_parameter("single_checkpoint", True).value)
        self.allow_int8 = bool(self.declare_parameter("allow_int8", False).value)
        valid_sensor_input_modes = {"auto", "camera_lidar", "camera_only"}
        if self.sensor_input_mode not in valid_sensor_input_modes:
            self.get_logger().warn(
                f"Unknown sensor_input_mode={self.sensor_input_mode}; falling back to auto"
            )
            self.sensor_input_mode = "auto"

        # camera + optional LiDAR + odometry + route proxy を揃えてから E2E 出力する。
        self.samples = {
            "image": LatestSample(),
            "camera_info": LatestSample(),
            "pointcloud": LatestSample(),
            "odom": LatestSample(),
            "target_point": LatestSample(),
            "target_path": LatestSample(),
            "route_command": LatestSample(),
        }
        self.last_target_triplet_status = {
            "source": "not_started",
            "target_path_topic": self.target_path_topic,
            "use_target_path_triplet": self.use_target_path_triplet,
            "frame_id": "",
            "frame_ok": False,
            "speed_mps": 0.0,
            "requested_distances_m": {},
            "actual_distances_m": {},
            "points": {},
        }

        # 起動時に一度だけ環境診断する。重い checkpoint load はここでは行わない。
        self.runtime_summary = inspect_lead_environment(
            lead_project_root=self.lead_project_root,
            model_path=self.model_path,
            model_variant=self.model_variant,
            runtime_mode=self.runtime_mode,
            precision_mode=self.precision_mode,
            allow_int8=self.allow_int8,
            disable_aux_heads=self.disable_aux_heads,
            single_checkpoint=self.single_checkpoint,
        )
        self.lead_runtime = None
        self.lead_forward_error = ""
        self.lead_preprocess_latency_ms = None
        self.lead_forward_latency_ms = None
        self.lead_forward_count = 0
        self.camera_info_source = "missing"
        self.synthetic_camera_info_count = 0
        if self.runtime_mode == "lead_python":
            self.lead_runtime = LeadTorchRuntime(
                lead_project_root=self.lead_project_root,
                model_path=self.model_path,
                device=self.runtime_device,
                precision_mode=self.precision_mode,
                disable_aux_heads=self.disable_aux_heads,
                single_checkpoint=self.single_checkpoint,
                strict_weight_load=self.lead_strict_weight_load,
                python_site=self.lead_python_site,
                torch_lib=self.lead_torch_lib,
                force_timm_pretrained_off=self.lead_force_timm_pretrained_off,
                input_preprocess_backend=self.input_preprocess_backend,
                lidar_raster_enabled=self.lead_lidar_raster_enabled,
                lidar_flip_y_axis=self.lead_lidar_flip_y_axis,
                lidar_history_size=self.lead_lidar_history_size,
                lidar_max_points=self.lead_lidar_max_points,
            )
            extra_roots = [FilePath.cwd(), _SOURCE_ROOT.parents[2]]
            if self.lead_runtime.load(extra_roots=extra_roots):
                self.runtime_summary["ready"] = True
                self.runtime_summary["blocking_reasons"] = []
                self.runtime_summary["runtime_device"] = self.runtime_device
                self.runtime_summary["checkpoint_files"] = self.lead_runtime.checkpoint_files
                self.get_logger().info(
                    "LEAD PyTorch runtime loaded "
                    f"device={self.runtime_device} "
                    f"checkpoints={len(self.lead_runtime.checkpoint_files)} "
                    f"disable_aux_heads={self.disable_aux_heads}"
                )
                if self.lead_probe_on_startup:
                    try:
                        probe = self.lead_runtime.synthetic_forward()
                        self.lead_forward_latency_ms = probe.latency_ms
                        self.lead_forward_count = self.lead_runtime.forward_count
                        self.get_logger().info(
                            "LEAD PyTorch synthetic forward OK "
                            f"device={probe.device} latency_ms={probe.latency_ms:.1f} "
                            f"path_points={len(probe.path_xy)}"
                        )
                    except Exception as exc:
                        self.lead_forward_error = f"{type(exc).__name__}: {exc}"
                        self.runtime_summary["ready"] = False
                        self.runtime_summary["blocking_reasons"] = [
                            f"LEAD synthetic forward failed: {self.lead_forward_error}"
                        ]
                        self.get_logger().error(
                            f"LEAD PyTorch synthetic forward failed: {self.lead_forward_error}"
                        )
            else:
                self.lead_forward_error = self.lead_runtime.error
                self.runtime_summary["ready"] = False
                self.runtime_summary["blocking_reasons"] = [self.lead_runtime.error]
                self.get_logger().warn(
                    f"LEAD PyTorch runtime not ready: {self.lead_runtime.error}"
                )

        self.image_topics = unique_topics(self.image_topic, self.image_fallback_topics)
        self.subscriptions_ = [
            *[
                self.create_subscription(
                    Image, topic, self.image_callback, qos_profile_sensor_data
                )
                for topic in self.image_topics
            ],
            self.create_subscription(
                CameraInfo,
                self.camera_info_topic,
                self.camera_info_callback,
                qos_profile_sensor_data,
            ),
            self.create_subscription(
                PointCloud2,
                self.pointcloud_topic,
                self.pointcloud_callback,
                qos_profile_sensor_data,
            ),
            self.create_subscription(Odometry, self.odom_topic, self.odom_callback, 10),
            self.create_subscription(
                PointStamped, self.target_point_topic, self.target_point_callback, 10
            ),
            self.create_subscription(Path, self.target_path_topic, self.target_path_callback, 10),
            self.create_subscription(String, self.route_command_topic, self.route_command_callback, 10),
        ]

        # 出力は shadow-mode 専用。実車制御 command には接続しない。
        self.path_pub = self.create_publisher(Path, "/shadow/e2e/path", 10)
        self.raw_lead_path_pub = (
            self.create_publisher(Path, self.raw_lead_path_topic, 10)
            if self.raw_lead_path_topic
            else None
        )
        self.steering_pub = self.create_publisher(Float32, "/shadow/e2e/steering_proxy", 10)
        self.curvature_pub = self.create_publisher(Float32, "/shadow/e2e/curvature", 10)
        self.speed_target_pub = self.create_publisher(Float32, "/shadow/e2e/speed_target", 10)
        self.confidence_pub = self.create_publisher(Float32, "/shadow/e2e/confidence", 10)
        self.status_pub = self.create_publisher(String, "/shadow/e2e/status", 10)
        self.marker_pub = self.create_publisher(MarkerArray, "/shadow/e2e/debug_markers", 10)

        timer_period = 1.0 / max(0.1, self.publish_rate_hz)
        self.timer = self.create_timer(timer_period, self.timer_callback)

        self.get_logger().info(
            "e2e_transfuser started "
            f"runtime={self.runtime_mode} precision={self.precision_mode} "
            f"sensor_input_mode={self.sensor_input_mode} images={self.image_topics}"
        )

    def image_callback(self, msg):
        now = self.get_clock().now()
        self.samples["image"].update(msg, now)
        self.ensure_camera_info_from_image(msg, now)

    def camera_info_callback(self, msg):
        self.samples["camera_info"].update(msg, self.get_clock().now())
        self.camera_info_source = "topic"

    def ensure_camera_info_from_image(self, image_msg, now):
        if not self.synthesize_camera_info_when_missing:
            return
        if self.samples["camera_info"].fresh(now, self.input_timeout_sec):
            return

        camera_info = CameraInfo()
        camera_info.header = image_msg.header
        if self.synthetic_camera_info_frame_id:
            camera_info.header.frame_id = str(self.synthetic_camera_info_frame_id)
        camera_info.width = image_msg.width
        camera_info.height = image_msg.height
        width = float(max(1, int(image_msg.width)))
        height = float(max(1, int(image_msg.height)))
        focal = self.synthetic_camera_info_focal_length_px
        if focal <= 0.0:
            focal = max(width, height)
        cx = width * 0.5
        cy = height * 0.5
        camera_info.k = [
            focal,
            0.0,
            cx,
            0.0,
            focal,
            cy,
            0.0,
            0.0,
            1.0,
        ]
        camera_info.p = [
            focal,
            0.0,
            cx,
            0.0,
            0.0,
            focal,
            cy,
            0.0,
            0.0,
            0.0,
            1.0,
            0.0,
        ]
        self.samples["camera_info"].update(camera_info, now)
        self.camera_info_source = "synthetic_from_image"
        self.synthetic_camera_info_count += 1

    def pointcloud_callback(self, msg):
        self.samples["pointcloud"].update(msg, self.get_clock().now())

    def odom_callback(self, msg):
        self.samples["odom"].update(msg, self.get_clock().now())

    def target_point_callback(self, msg):
        self.samples["target_point"].update(msg, self.get_clock().now())

    def target_path_callback(self, msg):
        self.samples["target_path"].update(msg, self.get_clock().now())

    def route_command_callback(self, msg):
        self.samples["route_command"].update(msg, self.get_clock().now())

    @staticmethod
    def clamp01(value):
        return min(1.0, max(0.0, value))

    def pointcloud_fresh(self, now):
        return self.samples["pointcloud"].fresh(now, self.input_timeout_sec)

    def active_sensor_input_mode(self, now):
        if self.sensor_input_mode == "camera_lidar":
            return "camera_lidar"
        if self.sensor_input_mode == "camera_only":
            return "camera_only"
        return "camera_lidar" if self.pointcloud_fresh(now) else "camera_only"

    def pointcloud_required(self, now):
        return self.active_sensor_input_mode(now) == "camera_lidar"

    def required_inputs(self, now):
        required = ["image", "camera_info"]
        if self.active_sensor_input_mode(now) == "camera_lidar":
            required.append("odom")
        if self.pointcloud_required(now):
            required.append("pointcloud")
        if self.require_target_point and self.active_sensor_input_mode(now) == "camera_lidar":
            required.append("target_point")
        return required

    def missing_optional_inputs(self, now):
        optional = []
        if not self.pointcloud_required(now) and not self.pointcloud_fresh(now):
            optional.append("pointcloud")
        if self.active_sensor_input_mode(now) == "camera_only":
            for name in ("odom", "target_point"):
                if not self.samples[name].fresh(now, self.input_timeout_sec):
                    optional.append(name)
        if self.use_target_path_triplet and not self.samples["target_path"].fresh(
            now, self.input_timeout_sec
        ):
            optional.append("target_path")
        return optional

    def lidar_frame_contract_status(self):
        raster_status = (
            self.lead_runtime.last_lidar_raster_status
            if self.lead_runtime is not None
            else {}
        )
        source = str(raster_status.get("source", ""))
        frame_id = str(raster_status.get("frame_id", ""))
        expected = list(self.lead_lidar_expected_frame_ids)
        frame_ok = not expected or (bool(frame_id) and frame_id in expected)
        if not self.lead_lidar_raster_enabled:
            state = "disabled"
        elif source != "pointcloud":
            state = "waiting_for_pointcloud"
        elif frame_ok:
            state = "ok"
        else:
            state = "unexpected_frame"
        reason = ""
        if state == "unexpected_frame":
            reason = "lidar raster input is used without TF transform; provide ego/body frame topic"
        return {
            "state": state,
            "pointcloud_topic": self.pointcloud_topic,
            "observed_frame_id": frame_id,
            "expected_frame_ids": expected,
            "frame_ok": frame_ok,
            "tf_transform_applied": False,
            "reason": reason,
        }

    def missing_inputs(self, now):
        # target point は route proxy。開発時は require_target_point=false で入力待ちを緩められる。
        return [
            name
            for name in self.required_inputs(now)
            if not self.samples[name].fresh(now, self.input_timeout_sec)
        ]

    def timer_callback(self):
        now = self.get_clock().now()
        active_sensor_input_mode = self.active_sensor_input_mode(now)
        missing = self.missing_inputs(now)
        input_ready = not missing
        confidence = 0.0
        path = None
        steering = 0.0
        curvature = 0.0
        speed_target = 0.0

        if input_ready and self.runtime_mode == "mock":
            path, steering, curvature, speed_target = self.run_mock_runtime(now)
            confidence = 1.0
            if active_sensor_input_mode == "camera_only":
                confidence *= self.camera_only_confidence_scale
            self.publish_outputs(path, steering, curvature, speed_target, confidence)
        elif input_ready and self.runtime_mode == "lead_python" and self.lead_runtime:
            result = self.run_lead_python_runtime(now)
            if result is not None:
                path, steering, curvature, speed_target, confidence = result
                if active_sensor_input_mode == "camera_only":
                    confidence *= self.camera_only_confidence_scale
                self.publish_outputs(path, steering, curvature, speed_target, confidence)
        elif input_ready:
            # 実モデル runtime は未接続でも、準備状態を confidence と status で可視化する。
            confidence = 0.2 if self.runtime_summary["ready"] else 0.05
            if active_sensor_input_mode == "camera_only":
                confidence *= self.camera_only_confidence_scale

        self.publish_status(now, input_ready, missing, confidence, active_sensor_input_mode)

    def run_lead_python_runtime(self, now):
        if self.lead_runtime is None or not self.lead_runtime.loaded:
            return None
        image_msg = self.samples["image"].msg
        if image_msg is None:
            return None
        pointcloud_msg = (
            self.samples["pointcloud"].msg
            if self.pointcloud_required(now)
            and self.samples["pointcloud"].fresh(now, self.input_timeout_sec)
            else None
        )
        try:
            target_points_xy = self.current_lead_target_points_xy(now)
            data = self.lead_runtime.build_data_from_ros(
                image_msg=image_msg,
                pointcloud_msg=pointcloud_msg,
                speed_mps=self.current_speed_mps(now),
                target_xy=target_points_xy["current"],
                target_points_xy=target_points_xy,
                command=self.current_route_command(),
            )
            forward = self.lead_runtime.forward(data)
            raw_path = self.path_from_xy(now, forward.path_xy)
            if self.raw_lead_path_pub is not None:
                self.raw_lead_path_pub.publish(raw_path)
            path = self.path_from_xy(now, self.lead_points_to_ros_points(forward.path_xy))
            steering, curvature = self.estimate_steering_from_path(path)
            self.lead_forward_latency_ms = forward.latency_ms
            self.lead_preprocess_latency_ms = self.lead_runtime.last_preprocess_latency_ms
            self.lead_forward_count = self.lead_runtime.forward_count
            self.lead_forward_error = ""
            confidence = forward.confidence
            return path, steering, curvature, forward.speed_target_mps, confidence
        except Exception as exc:
            self.lead_forward_error = f"{type(exc).__name__}: {exc}"
            self.get_logger().warn(
                f"LEAD PyTorch forward failed: {self.lead_forward_error}",
                throttle_duration_sec=2.0,
            )
            return None

    def current_target_xy(self):
        target_msg = self.samples["target_point"].msg
        if target_msg is not None:
            return float(target_msg.point.x), float(target_msg.point.y)
        return self.default_target_x_m, self.default_target_y_m

    def current_lead_target_xy(self):
        target_x, target_y = self.current_target_xy()
        if self.lead_flip_y_axis:
            target_y = -target_y
        return target_x, target_y

    def current_target_triplet_xy(self, now):
        fallback_current = self.current_target_xy()
        fallback = {
            "previous": fallback_current,
            "current": fallback_current,
            "next": fallback_current,
        }
        speed_status = self.current_speed_status(now)
        distances = self.target_path_requested_distances(speed_status["speed_mps"])
        source = "target_point"
        frame_id = self.current_target_frame_id()
        frame_ok = self.target_frame_ok(frame_id)
        reason = ""
        points = fallback
        fallback_distance = math.hypot(fallback_current[0], fallback_current[1])
        actual_distances = {label: fallback_distance for label in fallback}
        distance_reached = {label: False for label in fallback}

        path_sample = self.samples["target_path"]
        if self.use_target_path_triplet and path_sample.fresh(now, self.input_timeout_sec):
            path_msg = path_sample.msg
            path_frame = self.target_path_frame_id(path_msg, frame_id)
            path_frame_ok = self.target_frame_ok(path_frame)
            if path_msg is None or not path_msg.poses:
                reason = "empty_target_path"
            elif self.target_path_require_expected_frame and not path_frame_ok:
                reason = "unexpected_target_path_frame"
                frame_id = path_frame
                frame_ok = path_frame_ok
            else:
                selected = {
                    label: self.target_xy_from_path_distance_info(path_msg, distance)
                    for label, distance in distances.items()
                }
                if all(item["point"] is not None for item in selected.values()):
                    points = {label: item["point"] for label, item in selected.items()}
                    actual_distances = {
                        label: item["actual_distance_m"] for label, item in selected.items()
                    }
                    distance_reached = {
                        label: item["reached"] for label, item in selected.items()
                    }
                    source = "target_path"
                    frame_id = path_frame
                    frame_ok = path_frame_ok
                    if not all(distance_reached.values()):
                        reason = "target_path_shorter_than_requested"
                else:
                    reason = "target_path_has_no_forward_points"
                    frame_id = path_frame
                    frame_ok = path_frame_ok
        elif self.use_target_path_triplet:
            reason = "missing_or_stale_target_path"
        else:
            reason = "target_path_triplet_disabled"

        self.last_target_triplet_status = {
            "source": source,
            "reason": reason,
            "target_path_topic": self.target_path_topic,
            "target_point_topic": self.target_point_topic,
            "use_target_path_triplet": self.use_target_path_triplet,
            "target_path_require_expected_frame": self.target_path_require_expected_frame,
            "frame_id": frame_id,
            "expected_frame_ids": self.target_path_expected_frame_ids,
            "frame_ok": frame_ok,
            "speed_mps": speed_status["speed_mps"],
            "speed_source": speed_status["source"],
            "speed_age_sec": speed_status["age_sec"],
            "speed_fresh": speed_status["fresh"],
            "speed_adaptive": {
                "enabled": self.target_path_speed_adaptive,
                "lookahead_time_sec": self.target_path_speed_lookahead_time_sec,
                "base_current_distance_m": self.target_path_current_distance_m,
                "max_current_distance_m": self.target_path_max_current_distance_m,
            },
            "requested_distances_m": distances,
            "distances_m": distances,
            "actual_distances_m": actual_distances,
            "distance_reached": distance_reached,
            "points": {
                label: {"x": float(point[0]), "y": float(point[1])}
                for label, point in points.items()
            },
        }
        return points

    def target_path_requested_distances(self, speed_mps):
        base_current = max(0.0, self.target_path_current_distance_m)
        current = base_current
        if self.target_path_speed_adaptive:
            current += max(0.0, float(speed_mps)) * self.target_path_speed_lookahead_time_sec
            current = min(self.target_path_max_current_distance_m, max(base_current, current))

        if base_current > 1.0e-6:
            previous = current * max(0.0, self.target_path_previous_distance_m) / base_current
            next_point = current * max(base_current, self.target_path_next_distance_m) / base_current
        else:
            previous = max(0.0, self.target_path_previous_distance_m)
            next_point = max(current, self.target_path_next_distance_m)

        previous = min(current, max(self.target_path_min_forward_distance_m, previous))
        next_point = max(current, next_point)
        return {
            "previous": float(previous),
            "current": float(current),
            "next": float(next_point),
        }

    def current_lead_target_points_xy(self, now):
        points = self.current_target_triplet_xy(now)
        return {label: self.ros_target_to_lead(point) for label, point in points.items()}

    def ros_target_to_lead(self, point):
        x, y = point
        if self.lead_flip_y_axis:
            y = -y
        return x, y

    def current_target_frame_id(self):
        target_msg = self.samples["target_point"].msg
        if target_msg is not None and target_msg.header.frame_id:
            return str(target_msg.header.frame_id)
        return self.output_frame

    def target_frame_ok(self, frame_id):
        if not self.target_path_expected_frame_ids:
            return True
        return bool(frame_id) and frame_id in self.target_path_expected_frame_ids

    @staticmethod
    def target_path_frame_id(path_msg, fallback):
        if path_msg is None:
            return fallback
        if path_msg.header.frame_id:
            return str(path_msg.header.frame_id)
        for pose_stamped in path_msg.poses:
            if pose_stamped.header.frame_id:
                return str(pose_stamped.header.frame_id)
        return fallback

    def target_xy_from_path_distance_info(self, path_msg, distance_m):
        target_distance = max(0.0, float(distance_m))
        previous_x = 0.0
        previous_y = 0.0
        distance_accum = 0.0
        last_point = None
        last_distance = 0.0

        for pose_stamped in path_msg.poses:
            point = pose_stamped.pose.position
            x = float(point.x)
            y = float(point.y)
            if not (math.isfinite(x) and math.isfinite(y)):
                continue
            if x < self.target_path_min_forward_distance_m:
                continue
            segment = math.hypot(x - previous_x, y - previous_y)
            if segment <= 1.0e-6:
                last_point = (x, y)
                previous_x = x
                previous_y = y
                continue
            if distance_accum + segment >= target_distance:
                ratio = (target_distance - distance_accum) / segment
                ratio = min(1.0, max(0.0, ratio))
                return {
                    "point": (
                        previous_x + (x - previous_x) * ratio,
                        previous_y + (y - previous_y) * ratio,
                    ),
                    "actual_distance_m": target_distance,
                    "reached": True,
                }
            distance_accum += segment
            previous_x = x
            previous_y = y
            last_point = (x, y)
            last_distance = distance_accum
        return {
            "point": last_point,
            "actual_distance_m": last_distance if last_point is not None else None,
            "reached": False,
        }

    def target_xy_from_path_distance(self, path_msg, distance_m):
        return self.target_xy_from_path_distance_info(path_msg, distance_m)["point"]

    def lead_points_to_ros_points(self, points_xy):
        if not self.lead_flip_y_axis:
            return points_xy
        return [(x, -y) for x, y in points_xy]

    def current_speed_status(self, now=None):
        odom_sample = self.samples["odom"]
        odom_msg = odom_sample.msg
        age_sec = odom_sample.age_sec(now) if now is not None else None
        fresh = True if now is None else odom_sample.fresh(now, self.input_timeout_sec)
        if odom_msg is None:
            return {"speed_mps": 0.0, "source": "missing", "age_sec": age_sec, "fresh": False}
        if now is not None and not fresh:
            return {"speed_mps": 0.0, "source": "stale_odom", "age_sec": age_sec, "fresh": False}
        twist = odom_msg.twist.twist.linear
        speed_mps = math.sqrt(twist.x * twist.x + twist.y * twist.y + twist.z * twist.z)
        return {"speed_mps": speed_mps, "source": "odom", "age_sec": age_sec, "fresh": fresh}

    def current_speed_mps(self, now=None):
        return self.current_speed_status(now)["speed_mps"]

    def current_route_command(self):
        msg = self.samples["route_command"].msg
        if msg is None:
            return "lane_follow"
        return msg.data or "lane_follow"

    def run_mock_runtime(self, now):
        # mock は target point へ直線 waypoint を引く。ROS契約確認用で、走行品質評価用ではない。
        target_x, target_y = self.default_target_x_m, self.default_target_y_m
        target_msg = self.samples["target_point"].msg
        if target_msg is not None:
            target_x = float(target_msg.point.x)
            target_y = float(target_msg.point.y)

        distance = max(0.1, math.hypot(target_x, target_y))
        waypoint_count = max(2, self.max_waypoints)

        path = Path()
        path.header.stamp = now.to_msg()
        path.header.frame_id = self.output_frame

        for index in range(waypoint_count):
            ratio = float(index + 1) / float(waypoint_count)
            pose = PoseStamped()
            pose.header = path.header
            pose.pose.position.x = target_x * ratio
            pose.pose.position.y = target_y * ratio
            pose.pose.position.z = 0.0
            pose.pose.orientation.w = 1.0
            path.poses.append(pose)

        curvature = 2.0 * target_y / max(distance * distance, 0.1)
        steering = math.atan(self.wheel_base_m * curvature)

        # 速度目標は最低値を持たせ、停止 bag でも topic がゼロ固定になりすぎないようにする。
        odom = self.samples["odom"].msg
        vx = float(odom.twist.twist.linear.x) if odom is not None else 0.0
        vy = float(odom.twist.twist.linear.y) if odom is not None else 0.0
        speed_target = max(1.0, math.hypot(vx, vy))
        return path, steering, curvature, speed_target

    def path_from_xy(self, now, points_xy):
        path = Path()
        path.header.stamp = now.to_msg()
        path.header.frame_id = self.output_frame
        for x, y in points_xy[: self.max_waypoints]:
            pose = PoseStamped()
            pose.header = path.header
            pose.pose.position.x = float(x)
            pose.pose.position.y = float(y)
            pose.pose.position.z = 0.0
            pose.pose.orientation.w = 1.0
            path.poses.append(pose)
        return path

    def estimate_steering_from_path(self, path):
        if len(path.poses) < 2:
            return 0.0, 0.0
        target = path.poses[min(2, len(path.poses) - 1)].pose.position
        distance = max(0.1, math.hypot(target.x, target.y))
        curvature = 2.0 * target.y / max(distance * distance, 0.1)
        steering = math.atan(self.wheel_base_m * curvature)
        return steering, curvature

    def publish_outputs(self, path, steering, curvature, speed_target, confidence):
        self.path_pub.publish(path)
        self.steering_pub.publish(Float32(data=float(steering)))
        self.curvature_pub.publish(Float32(data=float(curvature)))
        self.speed_target_pub.publish(Float32(data=float(speed_target)))
        self.confidence_pub.publish(Float32(data=float(confidence)))
        if self.enable_debug_markers:
            self.marker_pub.publish(self.build_markers(path))

    def build_markers(self, path):
        marker_array = MarkerArray()
        line = Marker()
        line.header = path.header
        line.ns = "e2e_transfuser"
        line.id = 0
        line.type = Marker.LINE_STRIP
        line.action = Marker.ADD
        line.scale.x = 0.08
        line.color.r = 0.1
        line.color.g = 0.7
        line.color.b = 1.0
        line.color.a = 0.9
        line.points = [pose.pose.position for pose in path.poses]
        marker_array.markers.append(line)
        return marker_array

    def publish_status(self, now, input_ready, missing, confidence, active_sensor_input_mode):
        # GUI / replay tools から読めるよう、node状態とruntime診断をJSON文字列で流す。
        ages = {
            name: sample.age_sec(now)
            for name, sample in self.samples.items()
            if sample.age_sec(now) is not None
        }
        status = {
            "stamp": stamp_to_float(now.to_msg()),
            "model": self.model_variant,
            "runtime": self.runtime_mode,
            "precision": self.precision_mode,
            "runtime_device": self.runtime_device,
            "input_preprocess_backend": self.input_preprocess_backend,
            "camera_info_source": self.camera_info_source,
            "synthesize_camera_info_when_missing": self.synthesize_camera_info_when_missing,
            "synthetic_camera_info_count": self.synthetic_camera_info_count,
            "model_loaded": self.runtime_mode == "mock" or self.runtime_summary["ready"],
            "input_ready": input_ready,
            "missing_inputs": missing,
            "missing_optional_inputs": self.missing_optional_inputs(now),
            "configured_sensor_input_mode": self.sensor_input_mode,
            "active_sensor_input_mode": active_sensor_input_mode,
            "pointcloud_required": self.pointcloud_required(now),
            "input_age_sec": ages,
            "confidence": confidence,
            "frame_id": self.output_frame,
            "mode": "shadow_only",
            "lead_flip_y_axis": self.lead_flip_y_axis,
            "raw_lead_path_topic": self.raw_lead_path_topic,
            "lead_target_triplet": self.last_target_triplet_status,
            "disable_aux_heads": self.disable_aux_heads,
            "single_checkpoint": self.single_checkpoint,
            "allow_int8": self.allow_int8,
            "runtime_ready": self.runtime_summary["ready"],
            "runtime_blocking_reasons": self.runtime_summary["blocking_reasons"],
            "lead_forward_count": self.lead_forward_count,
            "lead_preprocess_latency_ms": self.lead_preprocess_latency_ms,
            "lead_forward_latency_ms": self.lead_forward_latency_ms,
            "lead_forward_error": self.lead_forward_error,
            "lead_lidar_raster_enabled": self.lead_lidar_raster_enabled,
            "lead_lidar_flip_y_axis": self.lead_lidar_flip_y_axis,
            "lead_lidar_history_size": self.lead_lidar_history_size,
            "lead_lidar_max_points": self.lead_lidar_max_points,
            "lead_lidar_expected_frame_ids": self.lead_lidar_expected_frame_ids,
            "lead_lidar_raster": (
                self.lead_runtime.last_lidar_raster_status
                if self.lead_runtime is not None
                else None
            ),
            "lead_lidar_frame_contract": self.lidar_frame_contract_status(),
        }
        self.status_pub.publish(String(data=json.dumps(status, sort_keys=True)))


def main(args=None):
    rclpy.init(args=args)
    node = E2ETransfuserNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    sys.exit(main())
