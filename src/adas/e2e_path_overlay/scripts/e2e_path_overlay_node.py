#!/usr/bin/env python3
import json
import math
import sys
from dataclasses import dataclass

import rclpy
from builtin_interfaces.msg import Time as TimeMsg
from nav_msgs.msg import Path
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rclpy.time import Time
from sensor_msgs.msg import CameraInfo, Image
from std_msgs.msg import String
import tf2_ros


SUPPORTED_ENCODINGS = {
    "rgb8": ("rgb", 3),
    "bgr8": ("bgr", 3),
    "rgba8": ("rgba", 4),
    "bgra8": ("bgra", 4),
    "mono8": ("mono", 1),
}


def stamp_to_sec(stamp):
    return float(stamp.sec) + float(stamp.nanosec) * 1.0e-9


@dataclass
class CameraModel:
    fx: float
    fy: float
    cx: float
    cy: float
    width: int
    height: int


@dataclass
class CameraTranslation:
    x: float
    y: float
    z: float
    source: str


class E2EPathOverlayNode(Node):
    def __init__(self):
        super().__init__("e2e_path_overlay")

        self.image_topic = self.declare_parameter(
            "image_topic", "/sensing/camera/camera0/image_rect_color"
        ).value
        self.camera_info_topic = self.declare_parameter(
            "camera_info_topic", "/sensing/camera/camera0/camera_info"
        ).value
        self.path_topic = self.declare_parameter("path_topic", "/shadow/e2e/path").value
        self.output_image_topic = self.declare_parameter(
            "output_image_topic", "/shadow/e2e/overlay_image"
        ).value
        self.output_status_topic = self.declare_parameter(
            "output_status_topic", "/shadow/e2e/overlay_status"
        ).value

        self.use_tf_translation = bool(
            self.declare_parameter("use_tf_translation", True).value
        )
        self.camera_x_m = float(self.declare_parameter("camera_x_m", 1.2).value)
        self.camera_y_m = float(self.declare_parameter("camera_y_m", 0.1).value)
        self.camera_z_m = float(self.declare_parameter("camera_z_m", 1.35).value)
        self.min_depth_m = float(self.declare_parameter("min_depth_m", 0.5).value)
        self.max_depth_m = float(self.declare_parameter("max_depth_m", 80.0).value)
        self.line_width_px = max(1, int(self.declare_parameter("line_width_px", 5).value))
        self.point_radius_px = max(
            1, int(self.declare_parameter("point_radius_px", 3).value)
        )
        self.draw_waypoints = bool(self.declare_parameter("draw_waypoints", True).value)
        self.stale_path_timeout_sec = float(
            self.declare_parameter("stale_path_timeout_sec", 1.0).value
        )
        self.stale_camera_info_timeout_sec = float(
            self.declare_parameter("stale_camera_info_timeout_sec", 2.0).value
        )
        color = self.declare_parameter("line_color_rgb", [0, 255, 80]).value
        self.line_color_rgb = tuple(max(0, min(255, int(value))) for value in color[:3])

        self.latest_path = None
        self.latest_path_received_at = None
        self.latest_camera_info = None
        self.latest_camera_info_received_at = None
        self.last_unsupported_encoding = None
        self.last_status_time = self.get_clock().now()

        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)

        self.image_sub = self.create_subscription(
            Image, self.image_topic, self.image_callback, qos_profile_sensor_data
        )
        self.camera_info_sub = self.create_subscription(
            CameraInfo,
            self.camera_info_topic,
            self.camera_info_callback,
            qos_profile_sensor_data,
        )
        self.path_sub = self.create_subscription(Path, self.path_topic, self.path_callback, 10)

        self.overlay_pub = self.create_publisher(Image, self.output_image_topic, 10)
        self.status_pub = self.create_publisher(String, self.output_status_topic, 10)

        self.get_logger().info(
            f"e2e_path_overlay started image={self.image_topic} path={self.path_topic}"
        )

    def camera_info_callback(self, msg):
        self.latest_camera_info = msg
        self.latest_camera_info_received_at = self.get_clock().now()

    def path_callback(self, msg):
        self.latest_path = msg
        self.latest_path_received_at = self.get_clock().now()

    def image_callback(self, msg):
        now = self.get_clock().now()
        encoding = msg.encoding.lower()
        if encoding not in SUPPORTED_ENCODINGS:
            self.publish_status(
                now,
                msg,
                projected_count=0,
                drawn_segments=0,
                skipped_reason=f"unsupported_encoding:{msg.encoding}",
            )
            if self.last_unsupported_encoding != msg.encoding:
                self.get_logger().warn(
                    f"Unsupported image encoding '{msg.encoding}'. "
                    "Supported: rgb8, bgr8, rgba8, bgra8, mono8."
                )
                self.last_unsupported_encoding = msg.encoding
            return

        camera_info_ready = self.is_fresh(
            self.latest_camera_info_received_at,
            now,
            self.stale_camera_info_timeout_sec,
        )
        path_ready = self.is_fresh(
            self.latest_path_received_at,
            now,
            self.stale_path_timeout_sec,
        )
        if not camera_info_ready or not path_ready:
            missing = []
            if not camera_info_ready:
                missing.append("camera_info")
            if not path_ready:
                missing.append("path")
            self.publish_status(
                now,
                msg,
                projected_count=0,
                drawn_segments=0,
                skipped_reason="missing_or_stale:" + ",".join(missing),
            )
            return

        camera_model = self.camera_model_from_info(self.latest_camera_info, msg)
        camera_translation = self.camera_translation(self.latest_path, msg)
        projected_points = self.project_path(
            self.latest_path, camera_model, camera_translation
        )

        overlay = Image()
        overlay.header = msg.header
        overlay.height = msg.height
        overlay.width = msg.width
        overlay.encoding = msg.encoding
        overlay.is_bigendian = msg.is_bigendian
        overlay.step = msg.step
        overlay.data = bytes(self.draw_overlay(msg, projected_points))

        self.overlay_pub.publish(overlay)
        drawn_segments = self.count_drawn_segments(projected_points)
        self.publish_status(
            now,
            msg,
            projected_count=sum(1 for point in projected_points if point is not None),
            drawn_segments=drawn_segments,
            skipped_reason="",
            camera_translation=camera_translation,
        )

    def is_fresh(self, received_at, now, timeout_sec):
        if received_at is None:
            return False
        age = (now - received_at).nanoseconds * 1.0e-9
        return 0.0 <= age <= timeout_sec

    def camera_model_from_info(self, camera_info, image):
        fx = float(camera_info.k[0])
        fy = float(camera_info.k[4])
        cx = float(camera_info.k[2])
        cy = float(camera_info.k[5])
        if fx <= 0.0 or fy <= 0.0:
            focal = max(float(image.width), float(image.height))
            fx = focal
            fy = focal
            cx = float(image.width) * 0.5
            cy = float(image.height) * 0.5
        return CameraModel(
            fx=fx,
            fy=fy,
            cx=cx,
            cy=cy,
            width=int(image.width),
            height=int(image.height),
        )

    def camera_translation(self, path, image):
        fallback = CameraTranslation(
            x=self.camera_x_m,
            y=self.camera_y_m,
            z=self.camera_z_m,
            source="parameter",
        )
        if not self.use_tf_translation:
            return fallback

        path_frame = path.header.frame_id
        camera_frame = image.header.frame_id or self.latest_camera_info.header.frame_id
        if not path_frame or not camera_frame:
            return fallback

        try:
            transform = self.tf_buffer.lookup_transform(
                path_frame,
                camera_frame,
                Time(),
                timeout=Duration(seconds=0.02),
            )
        except Exception:
            return fallback

        translation = transform.transform.translation
        return CameraTranslation(
            x=float(translation.x),
            y=float(translation.y),
            z=float(translation.z),
            source="tf",
        )

    def project_path(self, path, camera_model, camera_translation):
        projected = []
        for pose_stamped in path.poses:
            position = pose_stamped.pose.position
            dx = float(position.x) - camera_translation.x
            dy = float(position.y) - camera_translation.y
            dz = float(position.z) - camera_translation.z

            depth = dx
            if depth < self.min_depth_m or depth > self.max_depth_m:
                projected.append(None)
                continue

            image_x_m = -dy
            image_y_m = -dz
            u = camera_model.fx * image_x_m / depth + camera_model.cx
            v = camera_model.fy * image_y_m / depth + camera_model.cy
            if not math.isfinite(u) or not math.isfinite(v):
                projected.append(None)
                continue
            if u < 0 or u >= camera_model.width or v < 0 or v >= camera_model.height:
                projected.append(None)
                continue
            projected.append((int(round(u)), int(round(v))))
        return projected

    def draw_overlay(self, image, projected_points):
        buffer = bytearray(image.data)
        previous = None
        for point in projected_points:
            if point is None:
                previous = None
                continue
            if self.draw_waypoints:
                self.draw_disc(buffer, image, point[0], point[1], self.point_radius_px)
            if previous is not None:
                self.draw_line(buffer, image, previous, point, self.line_width_px)
            previous = point
        return buffer

    def draw_line(self, buffer, image, start, end, width):
        x0, y0 = start
        x1, y1 = end
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        error = dx + dy
        radius = max(0, width // 2)

        while True:
            self.draw_disc(buffer, image, x0, y0, radius)
            if x0 == x1 and y0 == y1:
                break
            error2 = 2 * error
            if error2 >= dy:
                error += dy
                x0 += sx
            if error2 <= dx:
                error += dx
                y0 += sy

    def draw_disc(self, buffer, image, center_x, center_y, radius):
        radius_sq = radius * radius
        for y in range(center_y - radius, center_y + radius + 1):
            if y < 0 or y >= image.height:
                continue
            for x in range(center_x - radius, center_x + radius + 1):
                if x < 0 or x >= image.width:
                    continue
                if (x - center_x) * (x - center_x) + (y - center_y) * (
                    y - center_y
                ) > radius_sq:
                    continue
                self.set_pixel(buffer, image, x, y)

    def set_pixel(self, buffer, image, x, y):
        layout, channels = SUPPORTED_ENCODINGS[image.encoding.lower()]
        offset = y * image.step + x * channels
        r, g, b = self.line_color_rgb
        if layout == "rgb":
            values = (r, g, b)
        elif layout == "bgr":
            values = (b, g, r)
        elif layout == "rgba":
            values = (r, g, b, 255)
        elif layout == "bgra":
            values = (b, g, r, 255)
        else:
            values = (max(r, g, b),)
        for index, value in enumerate(values):
            buffer[offset + index] = value

    def count_drawn_segments(self, projected_points):
        previous = None
        count = 0
        for point in projected_points:
            if point is None:
                previous = None
                continue
            if previous is not None:
                count += 1
            previous = point
        return count

    def publish_status(
        self,
        now,
        image,
        projected_count,
        drawn_segments,
        skipped_reason,
        camera_translation=None,
    ):
        if (now - self.last_status_time).nanoseconds < 0.2e9:
            return
        self.last_status_time = now
        payload = {
            "stamp": stamp_to_sec(now.to_msg()),
            "image_stamp": stamp_to_sec(image.header.stamp)
            if isinstance(image.header.stamp, TimeMsg)
            else 0.0,
            "image_frame": image.header.frame_id,
            "image_encoding": image.encoding,
            "path_topic": self.path_topic,
            "output_image_topic": self.output_image_topic,
            "projected_points": int(projected_count),
            "drawn_segments": int(drawn_segments),
            "skipped_reason": skipped_reason,
        }
        if camera_translation is not None:
            payload["camera_translation"] = {
                "x": camera_translation.x,
                "y": camera_translation.y,
                "z": camera_translation.z,
                "source": camera_translation.source,
            }
        self.status_pub.publish(String(data=json.dumps(payload, sort_keys=True)))


def main(args=None):
    rclpy.init(args=args)
    node = E2EPathOverlayNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    sys.exit(main())
