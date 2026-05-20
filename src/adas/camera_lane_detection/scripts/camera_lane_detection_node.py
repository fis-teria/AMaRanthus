#!/usr/bin/env python3
import json
import math
import os
import time
from typing import Optional

import cv2
import numpy as np
import rclpy
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Path
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
from sensor_msgs.msg import CameraInfo, Image
from std_msgs.msg import String


class CameraLaneDetectionNode(Node):
    def __init__(self) -> None:
        super().__init__("camera_lane_detection")

        self.enabled = bool(self.declare_parameter("enabled", True).value)
        self.backend = self.declare_parameter("backend", "opencv_classical").value
        self.model_path = self.declare_parameter("model_path", "").value
        self.image_topic = self.declare_parameter(
            "image_topic", "/sensing/camera/camera0/image_rect_color"
        ).value
        self.camera_info_topic = self.declare_parameter(
            "camera_info_topic", "/sensing/camera/camera0/camera_info"
        ).value
        self.output_path_topic = self.declare_parameter(
            "output_path_topic", "/shadow/perception/lane_path"
        ).value
        self.status_topic = self.declare_parameter(
            "status_topic", "/shadow/perception/lane_status"
        ).value
        self.output_frame = self.declare_parameter("output_frame", "base_link").value
        self.max_process_rate_hz = float(
            self.declare_parameter("max_process_rate_hz", 20.0).value
        )
        self.input_width = int(self.declare_parameter("input_width", 512).value)
        self.input_height = int(self.declare_parameter("input_height", 288).value)
        self.input_scale = float(
            self.declare_parameter("input_scale", 1.0 / 255.0).value
        )
        self.input_mean_rgb = self._vector_param("input_mean_rgb", [0.0, 0.0, 0.0])
        self.input_std_rgb = self._vector_param("input_std_rgb", [1.0, 1.0, 1.0])
        self.mask_threshold = float(self.declare_parameter("mask_threshold", 0.5).value)
        self.lane_class_ids = self._int_vector_param("lane_class_ids", [1])
        self.shoulder_class_ids = self._int_vector_param("shoulder_class_ids", [2])
        self.roi_top_ratio = float(self.declare_parameter("roi_top_ratio", 0.45).value)
        self.roi_bottom_ratio = float(
            self.declare_parameter("roi_bottom_ratio", 0.98).value
        )
        self.path_points = int(self.declare_parameter("path_points", 10).value)
        self.path_forward_min_m = float(
            self.declare_parameter("path_forward_min_m", 3.0).value
        )
        self.path_forward_max_m = float(
            self.declare_parameter("path_forward_max_m", 25.0).value
        )
        self.assumed_lane_width_m = float(
            self.declare_parameter("assumed_lane_width_m", 3.5).value
        )
        self.fallback_horizontal_fov_deg = float(
            self.declare_parameter("fallback_horizontal_fov_deg", 70.0).value
        )
        self.min_mask_pixels_per_band = int(
            self.declare_parameter("min_mask_pixels_per_band", 12).value
        )
        self.publish_status_every_frame = bool(
            self.declare_parameter("publish_status_every_frame", True).value
        )

        self.net = None
        self.model_error = ""
        self.last_process_time = 0.0
        self.latest_camera_info: Optional[CameraInfo] = None
        self.forward_count = 0
        self.last_latency_ms = 0.0
        self.image_sub = None
        self.camera_info_sub = None
        self.status_timer = None

        self._load_model()

        sensor_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )
        self.path_pub = self.create_publisher(Path, self.output_path_topic, 10)
        self.status_pub = self.create_publisher(String, self.status_topic, 10)

        if self.enabled and (self.net is not None or self.backend == "opencv_classical"):
            self.image_sub = self.create_subscription(
                Image, self.image_topic, self._on_image, sensor_qos
            )
            self.camera_info_sub = self.create_subscription(
                CameraInfo, self.camera_info_topic, self._on_camera_info, sensor_qos
            )
        else:
            period = 1.0 / max(0.1, min(self.max_process_rate_hz, 1.0))
            self.status_timer = self.create_timer(
                period,
                lambda: self._publish_status(
                    None,
                    published=False,
                    reason=self.model_error or "not_ready",
                ),
            )

        self.get_logger().info(
            "camera_lane_detection started "
            f"enabled={self.enabled} backend={self.backend} model={self.model_path or '<unset>'} "
            f"image_subscription={'on' if self.image_sub is not None else 'off'}"
        )

    def _vector_param(self, name: str, fallback: list[float]) -> np.ndarray:
        value = self.declare_parameter(name, fallback).value
        if len(value) != 3:
            value = fallback
        return np.asarray(value, dtype=np.float32)

    def _int_vector_param(self, name: str, fallback: list[int]) -> set[int]:
        value = self.declare_parameter(name, fallback).value
        return {int(item) for item in value}

    def _load_model(self) -> None:
        if not self.enabled:
            self.model_error = "disabled"
            return
        if self.backend == "opencv_classical":
            self.model_error = ""
            return
        if self.backend != "opencv_onnx":
            self.model_error = f"unsupported_backend:{self.backend}"
            return
        if not self.model_path:
            self.model_error = "missing_model_path"
            return
        model_path = os.path.expanduser(str(self.model_path))
        if not os.path.exists(model_path):
            self.model_error = f"model_not_found:{model_path}"
            return
        try:
            self.net = cv2.dnn.readNetFromONNX(model_path)
            self.model_error = ""
        except Exception as exc:
            self.net = None
            self.model_error = f"{type(exc).__name__}:{exc}"

    def _on_camera_info(self, msg: CameraInfo) -> None:
        self.latest_camera_info = msg

    def _on_image(self, msg: Image) -> None:
        now = time.monotonic()
        if self.max_process_rate_hz > 0.0:
            min_interval = 1.0 / self.max_process_rate_hz
            if now - self.last_process_time < min_interval:
                return
        self.last_process_time = now

        if not self.enabled or (self.net is None and self.backend != "opencv_classical"):
            if self.publish_status_every_frame:
                self._publish_status(msg, published=False, reason=self.model_error or "not_ready")
            return

        start = time.monotonic()
        try:
            rgb = self._image_to_rgb(msg)
            mask = self._run_segmentation(rgb)
            path = self._mask_to_path(mask, msg)
        except Exception as exc:
            self.model_error = f"{type(exc).__name__}:{exc}"
            self._publish_status(msg, published=False, reason=self.model_error)
            return

        self.last_latency_ms = (time.monotonic() - start) * 1000.0
        self.forward_count += 1
        if path.poses:
            self.path_pub.publish(path)
            self._publish_status(msg, published=True, reason="", path=path)
        else:
            self._publish_status(msg, published=False, reason="empty_lane_mask")

    def _image_to_rgb(self, msg: Image) -> np.ndarray:
        height = int(msg.height)
        width = int(msg.width)
        encoding = msg.encoding.lower()
        data = np.frombuffer(msg.data, dtype=np.uint8)
        if encoding == "rgb8":
            return data.reshape((height, width, 3)).copy()
        if encoding == "bgr8":
            bgr = data.reshape((height, width, 3))
            return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        if encoding == "mono8":
            mono = data.reshape((height, width))
            return cv2.cvtColor(mono, cv2.COLOR_GRAY2RGB)
        if encoding in ("yuv422", "uyvy", "uyvy422"):
            uyvy = data.reshape((height, width, 2))
            return cv2.cvtColor(uyvy, cv2.COLOR_YUV2RGB_UYVY)
        raise ValueError(f"unsupported image encoding: {msg.encoding}")

    def _run_segmentation(self, rgb: np.ndarray) -> np.ndarray:
        if self.backend == "opencv_classical":
            return self._run_classical_lane_mask(rgb)

        resized = cv2.resize(rgb, (self.input_width, self.input_height), interpolation=cv2.INTER_LINEAR)
        tensor = resized.astype(np.float32) * self.input_scale
        tensor = (tensor - self.input_mean_rgb) / np.maximum(self.input_std_rgb, 1.0e-6)
        blob = np.transpose(tensor, (2, 0, 1))[np.newaxis, ...]
        self.net.setInput(blob)
        output = self.net.forward()
        return self._output_to_mask(output, rgb.shape[1], rgb.shape[0])

    def _output_to_mask(self, output: np.ndarray, width: int, height: int) -> np.ndarray:
        output = np.asarray(output)
        if output.ndim == 4:
            output = output[0]
        if output.ndim == 3:
            if output.shape[0] > 1:
                class_map = np.argmax(output, axis=0).astype(np.int32)
                wanted = self.lane_class_ids | self.shoulder_class_ids
                mask = np.isin(class_map, list(wanted)).astype(np.uint8)
            else:
                mask = (output[0] >= self.mask_threshold).astype(np.uint8)
        elif output.ndim == 2:
            mask = (output >= self.mask_threshold).astype(np.uint8)
        else:
            raise ValueError(f"unsupported model output shape: {output.shape}")
        return cv2.resize(mask, (width, height), interpolation=cv2.INTER_NEAREST)

    def _run_classical_lane_mask(self, rgb: np.ndarray) -> np.ndarray:
        height, width = rgb.shape[:2]
        hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)

        white_mask = cv2.inRange(hsv, np.array([0, 0, 185]), np.array([180, 70, 255]))
        yellow_mask = cv2.inRange(hsv, np.array([15, 45, 90]), np.array([40, 255, 255]))
        mask = cv2.bitwise_or(white_mask, yellow_mask)

        roi = np.zeros((height, width), dtype=np.uint8)
        roi_top = int(np.clip(self.roi_top_ratio, 0.0, 1.0) * height)
        roi_bottom = int(np.clip(self.roi_bottom_ratio, 0.0, 1.0) * height)
        polygon = np.array(
            [
                [
                    (int(width * 0.08), roi_bottom),
                    (int(width * 0.40), roi_top),
                    (int(width * 0.60), roi_top),
                    (int(width * 0.92), roi_bottom),
                ]
            ],
            dtype=np.int32,
        )
        cv2.fillPoly(roi, polygon, 255)
        mask = cv2.bitwise_and(mask, roi)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        return (mask > 0).astype(np.uint8)

    def _mask_to_path(self, mask: np.ndarray, image_msg: Image) -> Path:
        height, width = mask.shape[:2]
        roi_top = int(np.clip(self.roi_top_ratio, 0.0, 1.0) * height)
        roi_bottom = int(np.clip(self.roi_bottom_ratio, 0.0, 1.0) * height)
        if roi_bottom <= roi_top:
            roi_top = int(0.45 * height)
            roi_bottom = int(0.98 * height)

        path = Path()
        path.header.stamp = image_msg.header.stamp
        path.header.frame_id = self.output_frame or image_msg.header.frame_id or "base_link"

        ys = np.linspace(roi_bottom - 1, roi_top, max(2, self.path_points)).astype(np.int32)
        image_center = 0.5 * float(width)
        for y in ys:
            band_half = max(2, height // 120)
            y0 = max(0, y - band_half)
            y1 = min(height, y + band_half + 1)
            xs = np.where(mask[y0:y1, :] > 0)[1]
            if xs.size < self.min_mask_pixels_per_band:
                continue

            left = xs[xs < image_center]
            right = xs[xs >= image_center]
            if left.size and right.size:
                left_edge = float(np.percentile(left, 85))
                right_edge = float(np.percentile(right, 15))
                center_u = 0.5 * (left_edge + right_edge)
                lane_width_px = max(1.0, right_edge - left_edge)
                meters_per_px = self.assumed_lane_width_m / lane_width_px
            else:
                center_u = float(np.median(xs))
                forward = self._row_to_forward_m(y, roi_top, roi_bottom)
                meters_per_px = self._meters_per_pixel(width, forward)

            forward = self._row_to_forward_m(y, roi_top, roi_bottom)
            lateral = (center_u - image_center) * meters_per_px
            pose = PoseStamped()
            pose.header = path.header
            pose.pose.position.x = float(forward)
            pose.pose.position.y = float(lateral)
            pose.pose.position.z = 0.0
            pose.pose.orientation.w = 1.0
            path.poses.append(pose)

        path.poses.sort(key=lambda pose: pose.pose.position.x)
        return path

    def _row_to_forward_m(self, y: int, roi_top: int, roi_bottom: int) -> float:
        denom = max(1.0, float(roi_bottom - roi_top))
        ratio = np.clip(float(roi_bottom - y) / denom, 0.0, 1.0)
        return self.path_forward_min_m + ratio * (
            self.path_forward_max_m - self.path_forward_min_m
        )

    def _meters_per_pixel(self, width: int, forward_m: float) -> float:
        if self.latest_camera_info is not None and self.latest_camera_info.k[0] > 1.0:
            fx = float(self.latest_camera_info.k[0])
            return max(0.001, forward_m / fx)
        half_fov = math.radians(self.fallback_horizontal_fov_deg) * 0.5
        return max(0.001, (forward_m * math.tan(half_fov)) / max(1.0, width * 0.5))

    def _publish_status(
        self,
        image_msg: Optional[Image],
        *,
        published: bool,
        reason: str,
        path: Optional[Path] = None,
    ) -> None:
        stamp = self.get_clock().now().nanoseconds * 1.0e-9
        image_encoding = ""
        image_height = 0
        image_width = 0
        if image_msg is not None:
            image_encoding = image_msg.encoding
            image_height = int(image_msg.height)
            image_width = int(image_msg.width)
            stamp = image_msg.header.stamp.sec + image_msg.header.stamp.nanosec * 1.0e-9
        payload = {
            "backend": self.backend,
            "enabled": self.enabled,
            "forward_count": self.forward_count,
            "image_encoding": image_encoding,
            "image_height": image_height,
            "image_subscription_active": self.image_sub is not None,
            "image_width": image_width,
            "latency_ms": self.last_latency_ms,
            "model_path": self.model_path,
            "published": published,
            "reason": reason,
            "path_points": 0 if path is None else len(path.poses),
            "stamp": stamp,
        }
        self.status_pub.publish(String(data=json.dumps(payload, sort_keys=True)))


def main() -> None:
    rclpy.init()
    node = CameraLaneDetectionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
