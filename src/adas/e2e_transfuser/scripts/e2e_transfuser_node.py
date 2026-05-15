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
        self.lead_strict_weight_load = bool(
            self.declare_parameter("lead_strict_weight_load", False).value
        )
        self.lead_probe_on_startup = bool(
            self.declare_parameter("lead_probe_on_startup", True).value
        )
        self.lead_force_timm_pretrained_off = bool(
            self.declare_parameter("lead_force_timm_pretrained_off", True).value
        )
        self.image_topic = self.declare_parameter(
            "image_topic", "/sensing/camera/camera0/image_rect_color"
        ).value
        self.image_fallback_topics = self.declare_parameter(
            "image_fallback_topics",
            ["/sensing/camera/camera0/image_rect_color", "/image_rect_color"],
        ).value
        self.camera_info_topic = self.declare_parameter(
            "camera_info_topic", "/sensing/camera/camera0/camera_info"
        ).value
        self.pointcloud_topic = self.declare_parameter("pointcloud_topic", "/livox/lidar").value
        self.sensor_input_mode = self.declare_parameter("sensor_input_mode", "auto").value
        self.odom_topic = self.declare_parameter("odom_topic", "/Odometry").value
        self.target_point_topic = self.declare_parameter(
            "target_point_topic", "/shadow/route/target_point"
        ).value
        self.route_command_topic = self.declare_parameter(
            "route_command_topic", "/shadow/route/command"
        ).value
        self.output_frame = self.declare_parameter("output_frame", "base_link").value
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
            "route_command": LatestSample(),
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
        self.lead_forward_latency_ms = None
        self.lead_forward_count = 0
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
            self.create_subscription(String, self.route_command_topic, self.route_command_callback, 10),
        ]

        # 出力は shadow-mode 専用。実車制御 command には接続しない。
        self.path_pub = self.create_publisher(Path, "/shadow/e2e/path", 10)
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
        self.samples["image"].update(msg, self.get_clock().now())

    def camera_info_callback(self, msg):
        self.samples["camera_info"].update(msg, self.get_clock().now())

    def pointcloud_callback(self, msg):
        self.samples["pointcloud"].update(msg, self.get_clock().now())

    def odom_callback(self, msg):
        self.samples["odom"].update(msg, self.get_clock().now())

    def target_point_callback(self, msg):
        self.samples["target_point"].update(msg, self.get_clock().now())

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
        return optional

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
        try:
            data = self.lead_runtime.build_data_from_ros(
                image_msg=image_msg,
                pointcloud_msg=self.samples["pointcloud"].msg,
                speed_mps=self.current_speed_mps(),
                target_xy=self.current_target_xy(),
                command=self.current_route_command(),
            )
            forward = self.lead_runtime.forward(data)
            path = self.path_from_xy(now, forward.path_xy)
            steering, curvature = self.estimate_steering_from_path(path)
            self.lead_forward_latency_ms = forward.latency_ms
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

    def current_speed_mps(self):
        odom_msg = self.samples["odom"].msg
        if odom_msg is None:
            return 0.0
        twist = odom_msg.twist.twist.linear
        return math.sqrt(twist.x * twist.x + twist.y * twist.y + twist.z * twist.z)

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
            "disable_aux_heads": self.disable_aux_heads,
            "single_checkpoint": self.single_checkpoint,
            "allow_int8": self.allow_int8,
            "runtime_ready": self.runtime_summary["ready"],
            "runtime_blocking_reasons": self.runtime_summary["blocking_reasons"],
            "lead_forward_count": self.lead_forward_count,
            "lead_forward_latency_ms": self.lead_forward_latency_ms,
            "lead_forward_error": self.lead_forward_error,
        }
        self.status_pub.publish(String(data=json.dumps(status, sort_keys=True)))


def main(args=None):
    rclpy.init(args=args)
    node = E2ETransfuserNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    sys.exit(main())
