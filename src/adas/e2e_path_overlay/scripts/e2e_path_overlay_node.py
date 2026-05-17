#!/usr/bin/env python3
import json
import math
import sys
from dataclasses import dataclass

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None
    np = None

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
from yolo_msgs.msg import DetectionArray


SUPPORTED_ENCODINGS = {
    "rgb8": ("rgb", 3),
    "bgr8": ("bgr", 3),
    "rgba8": ("rgba", 4),
    "bgra8": ("bgra", 4),
    "mono8": ("mono", 1),
}

YUV422_ENCODINGS = {
    "yuv422": "uyvy",
    "uyvy": "uyvy",
    "yuv422_yuy2": "yuyv",
    "yuyv": "yuyv",
    "yuy2": "yuyv",
}


def stamp_to_sec(stamp):
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


@dataclass
class ProjectedPathSample:
    center: tuple[int, int]
    left: tuple[int, int] | None
    right: tuple[int, int] | None
    depth_m: float


class E2EPathOverlayNode(Node):
    def __init__(self):
        super().__init__("e2e_path_overlay")

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
        self.path_topic = self.declare_parameter("path_topic", "/shadow/e2e/path").value
        self.yolo_detections_topic = self.declare_parameter(
            "yolo_detections_topic", "/yolo/tracking"
        ).value
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
        self.path_style = str(
            self.declare_parameter("path_style", "comma").value
        ).lower()
        self.path_ribbon_width_m = max(
            0.1, float(self.declare_parameter("path_ribbon_width_m", 2.8).value)
        )
        self.path_ribbon_alpha_near = max(
            0.0,
            min(1.0, float(self.declare_parameter("path_ribbon_alpha_near", 0.62).value)),
        )
        self.path_ribbon_alpha_far = max(
            0.0,
            min(1.0, float(self.declare_parameter("path_ribbon_alpha_far", 0.22).value)),
        )
        self.path_edge_width_px = max(
            0, int(self.declare_parameter("path_edge_width_px", 2).value)
        )
        self.draw_yolo_boxes = bool(
            self.declare_parameter("draw_yolo_boxes", True).value
        )
        self.yolo_min_score = float(self.declare_parameter("yolo_min_score", 0.25).value)
        self.yolo_box_width_px = max(
            1, int(self.declare_parameter("yolo_box_width_px", 3).value)
        )
        self.stale_path_timeout_sec = float(
            self.declare_parameter("stale_path_timeout_sec", 1.0).value
        )
        self.stale_yolo_timeout_sec = float(
            self.declare_parameter("stale_yolo_timeout_sec", 1.0).value
        )
        self.stale_camera_info_timeout_sec = float(
            self.declare_parameter("stale_camera_info_timeout_sec", 2.0).value
        )
        color = self.declare_parameter("line_color_rgb", [0, 255, 80]).value
        self.line_color_rgb = tuple(max(0, min(255, int(value))) for value in color[:3])
        ribbon_color = self.declare_parameter(
            "path_ribbon_color_rgb", [0, 210, 120]
        ).value
        self.path_ribbon_color_rgb = tuple(
            max(0, min(255, int(value))) for value in ribbon_color[:3]
        )
        edge_color = self.declare_parameter("path_edge_color_rgb", [180, 255, 210]).value
        self.path_edge_color_rgb = tuple(
            max(0, min(255, int(value))) for value in edge_color[:3]
        )
        yolo_color = self.declare_parameter("yolo_box_color_rgb", [255, 220, 0]).value
        self.yolo_box_color_rgb = tuple(
            max(0, min(255, int(value))) for value in yolo_color[:3]
        )

        self.latest_path = None
        self.latest_path_received_at = None
        self.latest_yolo_detections = None
        self.latest_yolo_received_at = None
        self.latest_camera_info = None
        self.latest_camera_info_received_at = None
        self.last_unsupported_encoding = None
        self.last_status_time = self.get_clock().now()

        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)

        self.image_topics = unique_topics(self.image_topic, self.image_fallback_topics)
        self.image_subs = [
            self.create_subscription(
                Image, topic, self.image_callback, qos_profile_sensor_data
            )
            for topic in self.image_topics
        ]
        self.camera_info_sub = self.create_subscription(
            CameraInfo,
            self.camera_info_topic,
            self.camera_info_callback,
            qos_profile_sensor_data,
        )
        self.path_sub = self.create_subscription(Path, self.path_topic, self.path_callback, 10)
        self.yolo_sub = self.create_subscription(
            DetectionArray,
            self.yolo_detections_topic,
            self.yolo_callback,
            qos_profile_sensor_data,
        )

        self.overlay_pub = self.create_publisher(Image, self.output_image_topic, 10)
        self.status_pub = self.create_publisher(String, self.output_status_topic, 10)

        self.get_logger().info(
            "e2e_path_overlay started "
            f"images={self.image_topics} path={self.path_topic} "
            f"yolo={self.yolo_detections_topic}"
        )

    def camera_info_callback(self, msg):
        self.latest_camera_info = msg
        self.latest_camera_info_received_at = self.get_clock().now()

    def path_callback(self, msg):
        self.latest_path = msg
        self.latest_path_received_at = self.get_clock().now()

    def yolo_callback(self, msg):
        self.latest_yolo_detections = msg
        self.latest_yolo_received_at = self.get_clock().now()

    def image_callback(self, msg):
        now = self.get_clock().now()
        encoding = msg.encoding.lower()
        if encoding in YUV422_ENCODINGS:
            converted = self.yuv422_to_rgb8_image(msg, YUV422_ENCODINGS[encoding])
            if converted is None:
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
                        "YUV422 input requires cv2 and numpy."
                    )
                    self.last_unsupported_encoding = msg.encoding
                return
            msg = converted
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
        yolo_boxes = self.fresh_yolo_boxes(now, msg)

        overlay = Image()
        overlay.header = msg.header
        overlay.height = msg.height
        overlay.width = msg.width
        overlay.encoding = msg.encoding
        overlay.is_bigendian = msg.is_bigendian
        overlay.step = msg.step
        overlay.data = bytes(self.draw_overlay(msg, projected_points, yolo_boxes))

        self.overlay_pub.publish(overlay)
        drawn_segments = self.count_drawn_segments(projected_points)
        self.publish_status(
            now,
            msg,
            projected_count=sum(1 for point in projected_points if point is not None),
            drawn_segments=drawn_segments,
            yolo_box_count=len(yolo_boxes),
            skipped_reason="",
            camera_translation=camera_translation,
        )

    def yuv422_to_rgb8_image(self, image, layout):
        if cv2 is None or np is None:
            return None
        width = int(image.width)
        height = int(image.height)
        step = int(image.step)
        try:
            raw = np.frombuffer(image.data, dtype=np.uint8).reshape((height, step))
            yuv = raw[:, : width * 2].reshape((height, width, 2))
            code = cv2.COLOR_YUV2RGB_UYVY if layout == "uyvy" else cv2.COLOR_YUV2RGB_YUY2
            rgb = cv2.cvtColor(yuv, code)
        except ValueError:
            return None

        converted = Image()
        converted.header = image.header
        converted.height = image.height
        converted.width = image.width
        converted.encoding = "rgb8"
        converted.is_bigendian = 0
        converted.step = width * 3
        converted.data = rgb.tobytes()
        return converted

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
            center = self.project_world_point(
                float(position.x),
                float(position.y),
                float(position.z),
                camera_model,
                camera_translation,
            )
            if center is None:
                projected.append(None)
                continue

            half_width = self.path_ribbon_width_m * 0.5
            left = self.project_world_point(
                float(position.x),
                float(position.y) + half_width,
                float(position.z),
                camera_model,
                camera_translation,
            )
            right = self.project_world_point(
                float(position.x),
                float(position.y) - half_width,
                float(position.z),
                camera_model,
                camera_translation,
            )
            projected.append(
                ProjectedPathSample(
                    center=center[0],
                    left=left[0] if left is not None else None,
                    right=right[0] if right is not None else None,
                    depth_m=center[1],
                )
            )
        return projected

    def project_world_point(self, x_m, y_m, z_m, camera_model, camera_translation):
        dx = x_m - camera_translation.x
        dy = y_m - camera_translation.y
        dz = z_m - camera_translation.z

        depth = dx
        if depth < self.min_depth_m or depth > self.max_depth_m:
            return None

        image_x_m = -dy
        image_y_m = -dz
        u = camera_model.fx * image_x_m / depth + camera_model.cx
        v = camera_model.fy * image_y_m / depth + camera_model.cy
        if not math.isfinite(u) or not math.isfinite(v):
            return None
        if u < 0 or u >= camera_model.width or v < 0 or v >= camera_model.height:
            return None
        return (int(round(u)), int(round(v))), depth

    def fresh_yolo_boxes(self, now, image):
        if not self.draw_yolo_boxes:
            return []
        if not self.is_fresh(
            self.latest_yolo_received_at, now, self.stale_yolo_timeout_sec
        ):
            return []

        boxes = []
        for detection in self.latest_yolo_detections.detections:
            if float(detection.score) < self.yolo_min_score:
                continue

            center = detection.bbox.center.position
            size = detection.bbox.size
            width = float(size.x)
            height = float(size.y)
            if width <= 0.0 or height <= 0.0:
                continue

            left = int(round(float(center.x) - width * 0.5))
            top = int(round(float(center.y) - height * 0.5))
            right = int(round(float(center.x) + width * 0.5))
            bottom = int(round(float(center.y) + height * 0.5))

            if right < 0 or bottom < 0 or left >= image.width or top >= image.height:
                continue

            boxes.append(
                (
                    max(0, left),
                    max(0, top),
                    min(int(image.width) - 1, right),
                    min(int(image.height) - 1, bottom),
                )
            )
        return boxes

    def draw_overlay(self, image, projected_points, yolo_boxes):
        buffer = bytearray(image.data)
        image_array = self.image_array_from_buffer(buffer, image)

        if image_array is not None and self.path_style == "comma":
            self.draw_comma_path_cv(image_array, image, projected_points)
        elif self.path_style == "comma":
            self.draw_comma_path(buffer, image, projected_points)
        else:
            self.draw_legacy_path(buffer, image, projected_points)

        for box in yolo_boxes:
            if image_array is not None:
                self.draw_rectangle_cv(image_array, image, box, self.yolo_box_width_px)
            else:
                self.draw_rectangle(buffer, image, box, self.yolo_box_width_px)
        return buffer

    def image_array_from_buffer(self, buffer, image):
        if cv2 is None or np is None:
            return None
        layout, channels = SUPPORTED_ENCODINGS[image.encoding.lower()]
        try:
            raw = np.frombuffer(buffer, dtype=np.uint8).reshape((int(image.height), int(image.step)))
            if layout == "mono":
                return raw[:, : int(image.width)]
            return raw[:, : int(image.width) * channels].reshape(
                (int(image.height), int(image.width), channels)
            )
        except ValueError:
            return None

    def draw_comma_path_cv(self, image_array, image, projected_points):
        previous = None
        for sample in projected_points:
            if sample is None:
                previous = None
                continue
            if previous is not None:
                self.draw_path_ribbon_segment_cv(image_array, image, previous, sample)
            previous = sample

        if self.draw_waypoints:
            color = self.color_for_encoding(image, self.path_edge_color_rgb)
            for sample in projected_points:
                if sample is None:
                    continue
                cv2.circle(
                    image_array,
                    sample.center,
                    self.point_radius_px,
                    color,
                    thickness=-1,
                    lineType=cv2.LINE_AA,
                )

    def draw_path_ribbon_segment_cv(self, image_array, image, start, end):
        if start.left is None or start.right is None or end.left is None or end.right is None:
            color = self.color_for_encoding(image, self.line_color_rgb)
            cv2.line(
                image_array,
                start.center,
                end.center,
                color,
                thickness=self.line_width_px,
                lineType=cv2.LINE_AA,
            )
            return

        avg_depth = (start.depth_m + end.depth_m) * 0.5
        depth_ratio = max(0.0, min(1.0, avg_depth / max(self.max_depth_m, 0.1)))
        alpha = self.path_ribbon_alpha_near + (
            self.path_ribbon_alpha_far - self.path_ribbon_alpha_near
        ) * depth_ratio
        points = np.array([start.left, end.left, end.right, start.right], dtype=np.int32)
        self.fill_polygon_cv(
            image_array,
            points,
            self.color_for_encoding(image, self.path_ribbon_color_rgb),
            alpha,
        )

        if self.path_edge_width_px > 0:
            edge_color = self.color_for_encoding(image, self.path_edge_color_rgb)
            cv2.line(
                image_array,
                start.left,
                end.left,
                edge_color,
                thickness=self.path_edge_width_px,
                lineType=cv2.LINE_AA,
            )
            cv2.line(
                image_array,
                start.right,
                end.right,
                edge_color,
                thickness=self.path_edge_width_px,
                lineType=cv2.LINE_AA,
            )

    def fill_polygon_cv(self, image_array, points, color, alpha):
        min_x = max(0, int(points[:, 0].min()))
        max_x = min(image_array.shape[1] - 1, int(points[:, 0].max()))
        min_y = max(0, int(points[:, 1].min()))
        max_y = min(image_array.shape[0] - 1, int(points[:, 1].max()))
        if min_x > max_x or min_y > max_y:
            return

        roi = image_array[min_y : max_y + 1, min_x : max_x + 1]
        if roi.size == 0:
            return
        local_points = points.copy()
        local_points[:, 0] -= min_x
        local_points[:, 1] -= min_y

        overlay = roi.copy()
        cv2.fillConvexPoly(overlay, local_points, color, lineType=cv2.LINE_AA)
        cv2.addWeighted(overlay, alpha, roi, 1.0 - alpha, 0.0, dst=roi)

    def draw_rectangle_cv(self, image_array, image, box, width):
        left, top, right, bottom = box
        cv2.rectangle(
            image_array,
            (left, top),
            (right, bottom),
            self.color_for_encoding(image, self.yolo_box_color_rgb),
            thickness=width,
            lineType=cv2.LINE_AA,
        )

    def color_for_encoding(self, image, color_rgb):
        layout, channels = SUPPORTED_ENCODINGS[image.encoding.lower()]
        r, g, b = color_rgb
        if layout == "rgb":
            return (r, g, b)
        if layout == "bgr":
            return (b, g, r)
        if layout == "rgba":
            return (r, g, b, 255)
        if layout == "bgra":
            return (b, g, r, 255)
        return (max(r, g, b),)

    def draw_legacy_path(self, buffer, image, projected_points):
        previous = None
        for sample in projected_points:
            if sample is None:
                previous = None
                continue
            point = sample.center
            if self.draw_waypoints:
                self.draw_disc(
                    buffer,
                    image,
                    point[0],
                    point[1],
                    self.point_radius_px,
                    self.line_color_rgb,
                )
            if previous is not None:
                self.draw_line(buffer, image, previous, point, self.line_width_px)
            previous = point

    def draw_comma_path(self, buffer, image, projected_points):
        previous = None
        for sample in projected_points:
            if sample is None:
                previous = None
                continue
            if previous is not None:
                self.draw_path_ribbon_segment(buffer, image, previous, sample)
            previous = sample

        if self.draw_waypoints:
            for sample in projected_points:
                if sample is None:
                    continue
                self.draw_disc(
                    buffer,
                    image,
                    sample.center[0],
                    sample.center[1],
                    self.point_radius_px,
                    self.path_edge_color_rgb,
                )

    def draw_path_ribbon_segment(self, buffer, image, start, end):
        if start.left is None or start.right is None or end.left is None or end.right is None:
            self.draw_line(buffer, image, start.center, end.center, self.line_width_px)
            return

        avg_depth = (start.depth_m + end.depth_m) * 0.5
        depth_ratio = max(0.0, min(1.0, avg_depth / max(self.max_depth_m, 0.1)))
        alpha = self.path_ribbon_alpha_near + (
            self.path_ribbon_alpha_far - self.path_ribbon_alpha_near
        ) * depth_ratio
        polygon = [start.left, end.left, end.right, start.right]
        self.fill_polygon(buffer, image, polygon, self.path_ribbon_color_rgb, alpha)

        if self.path_edge_width_px > 0:
            self.draw_line_with_color(
                buffer,
                image,
                start.left,
                end.left,
                self.path_edge_width_px,
                self.path_edge_color_rgb,
            )
            self.draw_line_with_color(
                buffer,
                image,
                start.right,
                end.right,
                self.path_edge_width_px,
                self.path_edge_color_rgb,
            )

    def fill_polygon(self, buffer, image, points, color_rgb, alpha):
        if len(points) < 3:
            return
        min_y = max(0, min(point[1] for point in points))
        max_y = min(int(image.height) - 1, max(point[1] for point in points))
        if min_y > max_y:
            return

        for y in range(min_y, max_y + 1):
            intersections = []
            for index, start in enumerate(points):
                end = points[(index + 1) % len(points)]
                y0 = start[1]
                y1 = end[1]
                if y0 == y1:
                    continue
                if y < min(y0, y1) or y >= max(y0, y1):
                    continue
                x0 = start[0]
                x1 = end[0]
                t = (y - y0) / float(y1 - y0)
                intersections.append(x0 + t * (x1 - x0))

            intersections.sort()
            for index in range(0, len(intersections) - 1, 2):
                x0 = max(0, int(math.ceil(intersections[index])))
                x1 = min(int(image.width) - 1, int(math.floor(intersections[index + 1])))
                for x in range(x0, x1 + 1):
                    self.blend_pixel(buffer, image, x, y, color_rgb, alpha)

    def draw_line(self, buffer, image, start, end, width):
        self.draw_line_with_color(buffer, image, start, end, width, self.line_color_rgb)

    def draw_line_with_color(self, buffer, image, start, end, width, color_rgb):
        x0, y0 = start
        x1, y1 = end
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        error = dx + dy
        radius = max(0, width // 2)

        while True:
            self.draw_disc(buffer, image, x0, y0, radius, color_rgb)
            if x0 == x1 and y0 == y1:
                break
            error2 = 2 * error
            if error2 >= dy:
                error += dy
                x0 += sx
            if error2 <= dx:
                error += dx
                y0 += sy

    def draw_rectangle(self, buffer, image, box, width):
        left, top, right, bottom = box
        for offset in range(width):
            self.draw_horizontal_line(
                buffer, image, left, right, top + offset, self.yolo_box_color_rgb
            )
            self.draw_horizontal_line(
                buffer, image, left, right, bottom - offset, self.yolo_box_color_rgb
            )
            self.draw_vertical_line(
                buffer, image, left + offset, top, bottom, self.yolo_box_color_rgb
            )
            self.draw_vertical_line(
                buffer, image, right - offset, top, bottom, self.yolo_box_color_rgb
            )

    def draw_horizontal_line(self, buffer, image, x0, x1, y, color_rgb):
        if y < 0 or y >= image.height:
            return
        start = max(0, min(x0, x1))
        end = min(int(image.width) - 1, max(x0, x1))
        for x in range(start, end + 1):
            self.set_pixel(buffer, image, x, y, color_rgb)

    def draw_vertical_line(self, buffer, image, x, y0, y1, color_rgb):
        if x < 0 or x >= image.width:
            return
        start = max(0, min(y0, y1))
        end = min(int(image.height) - 1, max(y0, y1))
        for y in range(start, end + 1):
            self.set_pixel(buffer, image, x, y, color_rgb)

    def draw_disc(self, buffer, image, center_x, center_y, radius, color_rgb):
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
                self.set_pixel(buffer, image, x, y, color_rgb)

    def set_pixel(self, buffer, image, x, y, color_rgb):
        layout, channels = SUPPORTED_ENCODINGS[image.encoding.lower()]
        offset = y * image.step + x * channels
        r, g, b = color_rgb
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

    def blend_pixel(self, buffer, image, x, y, color_rgb, alpha):
        layout, channels = SUPPORTED_ENCODINGS[image.encoding.lower()]
        offset = y * image.step + x * channels
        r, g, b = color_rgb
        alpha = max(0.0, min(1.0, alpha))

        if layout == "rgb":
            values = (r, g, b)
            indexes = (0, 1, 2)
        elif layout == "bgr":
            values = (b, g, r)
            indexes = (0, 1, 2)
        elif layout == "rgba":
            values = (r, g, b)
            indexes = (0, 1, 2)
        elif layout == "bgra":
            values = (b, g, r)
            indexes = (0, 1, 2)
        else:
            values = (max(r, g, b),)
            indexes = (0,)

        for index, value in zip(indexes, values):
            current = buffer[offset + index]
            buffer[offset + index] = int(round(current * (1.0 - alpha) + value * alpha))
        if layout in ("rgba", "bgra") and channels == 4:
            buffer[offset + 3] = 255

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
        yolo_box_count=0,
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
            "path_style": self.path_style,
            "projected_points": int(projected_count),
            "drawn_segments": int(drawn_segments),
            "yolo_detections_topic": self.yolo_detections_topic,
            "yolo_boxes": int(yolo_box_count),
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
