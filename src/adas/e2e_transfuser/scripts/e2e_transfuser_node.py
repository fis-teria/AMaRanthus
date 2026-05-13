#!/usr/bin/env python3
import json
import math
from pathlib import Path
import sys

_SOURCE_ROOT = Path(__file__).resolve().parents[1]
if (_SOURCE_ROOT / "e2e_transfuser").exists():
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


def stamp_to_float(stamp):
    return float(stamp.sec) + float(stamp.nanosec) * 1.0e-9


class LatestSample:
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

        self.runtime_mode = self.declare_parameter("runtime_mode", "mock").value
        self.precision_mode = self.declare_parameter("precision_mode", "fp32").value
        self.model_variant = self.declare_parameter("model_variant", "tfv6_resnet34").value
        self.model_path = self.declare_parameter(
            "model_path", "Data/models/tfv6/tfv6_resnet34"
        ).value
        self.lead_project_root = self.declare_parameter("lead_project_root", "").value
        self.image_topic = self.declare_parameter(
            "image_topic", "/sensing/camera/camera0/image_rect_color"
        ).value
        self.camera_info_topic = self.declare_parameter(
            "camera_info_topic", "/sensing/camera/camera0/camera_info"
        ).value
        self.pointcloud_topic = self.declare_parameter("pointcloud_topic", "/livox/lidar").value
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

        self.samples = {
            "image": LatestSample(),
            "camera_info": LatestSample(),
            "pointcloud": LatestSample(),
            "odom": LatestSample(),
            "target_point": LatestSample(),
            "route_command": LatestSample(),
        }

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

        self.subscriptions_ = [
            self.create_subscription(
                Image, self.image_topic, self.image_callback, qos_profile_sensor_data
            ),
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
            f"e2e_transfuser started runtime={self.runtime_mode} precision={self.precision_mode}"
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

    def missing_inputs(self, now):
        required = ["image", "camera_info", "pointcloud", "odom"]
        if self.require_target_point:
            required.append("target_point")
        return [
            name
            for name in required
            if not self.samples[name].fresh(now, self.input_timeout_sec)
        ]

    def timer_callback(self):
        now = self.get_clock().now()
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
            self.publish_outputs(path, steering, curvature, speed_target, confidence)
        elif input_ready:
            confidence = 0.2 if self.runtime_summary["ready"] else 0.05

        self.publish_status(now, input_ready, missing, confidence)

    def run_mock_runtime(self, now):
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

        odom = self.samples["odom"].msg
        vx = float(odom.twist.twist.linear.x) if odom is not None else 0.0
        vy = float(odom.twist.twist.linear.y) if odom is not None else 0.0
        speed_target = max(1.0, math.hypot(vx, vy))
        return path, steering, curvature, speed_target

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

    def publish_status(self, now, input_ready, missing, confidence):
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
            "model_loaded": self.runtime_mode == "mock" or self.runtime_summary["ready"],
            "input_ready": input_ready,
            "missing_inputs": missing,
            "input_age_sec": ages,
            "confidence": confidence,
            "frame_id": self.output_frame,
            "mode": "shadow_only",
            "disable_aux_heads": self.disable_aux_heads,
            "single_checkpoint": self.single_checkpoint,
            "allow_int8": self.allow_int8,
            "runtime_ready": self.runtime_summary["ready"],
            "runtime_blocking_reasons": self.runtime_summary["blocking_reasons"],
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
