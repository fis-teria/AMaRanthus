#!/usr/bin/env python3
from dataclasses import dataclass, field
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


@dataclass
class LaneFitDebug:
    confidence: float = 0.0
    left_band_count: int = 0
    right_band_count: int = 0
    both_band_count: int = 0
    mask_pixels: int = 0
    observed_lane_width_m: Optional[float] = None
    smoothed: bool = False
    reason: str = ""
    left_pixels: list[tuple[int, int]] = field(default_factory=list)
    right_pixels: list[tuple[int, int]] = field(default_factory=list)


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
        self.debug_mask_topic = self.declare_parameter(
            "debug_mask_topic", "/shadow/perception/lane_mask"
        ).value
        self.debug_image_topic = self.declare_parameter(
            "debug_image_topic", "/shadow/perception/lane_debug_image"
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
        self.publish_debug_images = bool(
            self.declare_parameter("publish_debug_images", False).value
        )
        self.white_hsv_low = self._int_array_param("white_hsv_low", [0, 0, 185])
        self.white_hsv_high = self._int_array_param("white_hsv_high", [180, 70, 255])
        self.yellow_hsv_low = self._int_array_param("yellow_hsv_low", [15, 45, 90])
        self.yellow_hsv_high = self._int_array_param("yellow_hsv_high", [40, 255, 255])
        self.roi_left_bottom_ratio = float(
            self.declare_parameter("roi_left_bottom_ratio", 0.08).value
        )
        self.roi_left_top_ratio = float(
            self.declare_parameter("roi_left_top_ratio", 0.40).value
        )
        self.roi_right_top_ratio = float(
            self.declare_parameter("roi_right_top_ratio", 0.60).value
        )
        self.roi_right_bottom_ratio = float(
            self.declare_parameter("roi_right_bottom_ratio", 0.92).value
        )
        self.morph_kernel_size = max(
            1, int(self.declare_parameter("morph_kernel_size", 5).value)
        )
        if self.morph_kernel_size % 2 == 0:
            self.morph_kernel_size += 1
        self.min_fit_points_per_side = max(
            2, int(self.declare_parameter("min_fit_points_per_side", 3).value)
        )
        self.min_lane_confidence = max(
            0.0, min(1.0, float(self.declare_parameter("min_lane_confidence", 0.25).value))
        )
        self.smoothing_alpha = max(
            0.0, min(1.0, float(self.declare_parameter("smoothing_alpha", 0.35).value))
        )
        self.max_smoothing_jump_m = max(
            0.1, float(self.declare_parameter("max_smoothing_jump_m", 1.5).value)
        )
        self.min_lane_width_m = max(
            0.1, float(self.declare_parameter("min_lane_width_m", 2.2).value)
        )
        self.max_lane_width_m = max(
            self.min_lane_width_m,
            float(self.declare_parameter("max_lane_width_m", 4.8).value),
        )
        self.max_abs_lateral_m = max(
            0.1, float(self.declare_parameter("max_abs_lateral_m", 5.0).value)
        )

        self.net = None
        self.model_error = ""
        self.last_process_time = 0.0
        self.latest_camera_info: Optional[CameraInfo] = None
        self.forward_count = 0
        self.last_latency_ms = 0.0
        self.last_lane_confidence = 0.0
        self.smoothed_laterals: Optional[np.ndarray] = None
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
        self.debug_mask_pub = (
            self.create_publisher(Image, self.debug_mask_topic, 10)
            if self.publish_debug_images
            else None
        )
        self.debug_image_pub = (
            self.create_publisher(Image, self.debug_image_topic, 10)
            if self.publish_debug_images
            else None
        )

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

    def _int_array_param(self, name: str, fallback: list[int]) -> np.ndarray:
        value = self.declare_parameter(name, fallback).value
        try:
            items = list(value)
        except TypeError:
            items = fallback
        if len(items) != len(fallback):
            items = fallback
        return np.asarray([max(0, min(255, int(item))) for item in items], dtype=np.uint8)

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
            path, debug = self._mask_to_path(mask, msg)
        except Exception as exc:
            self.model_error = f"{type(exc).__name__}:{exc}"
            self._publish_status(msg, published=False, reason=self.model_error)
            return

        self.last_latency_ms = (time.monotonic() - start) * 1000.0
        self.forward_count += 1
        self.last_lane_confidence = debug.confidence
        if self.publish_debug_images:
            self._publish_debug_images(msg, rgb, mask, path, debug)
        if path.poses and debug.confidence >= self.min_lane_confidence:
            self.path_pub.publish(path)
            self._publish_status(msg, published=True, reason="", path=path, debug=debug)
        else:
            reason = debug.reason or "empty_lane_mask"
            if path.poses and debug.confidence < self.min_lane_confidence:
                reason = "low_lane_confidence"
            self._publish_status(msg, published=False, reason=reason, path=path, debug=debug)

    def _image_to_rgb(self, msg: Image) -> np.ndarray:
        height = int(msg.height)
        width = int(msg.width)
        encoding = msg.encoding.lower()
        if encoding == "rgb8":
            rows = self._image_rows(msg, width * 3)
            return rows[:, : width * 3].reshape((height, width, 3)).copy()
        if encoding == "bgr8":
            rows = self._image_rows(msg, width * 3)
            bgr = rows[:, : width * 3].reshape((height, width, 3))
            return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        if encoding == "mono8":
            rows = self._image_rows(msg, width)
            mono = rows[:, :width].reshape((height, width))
            return cv2.cvtColor(mono, cv2.COLOR_GRAY2RGB)
        if encoding in ("yuv422", "uyvy", "uyvy422"):
            rows = self._image_rows(msg, width * 2)
            uyvy = rows[:, : width * 2].reshape((height, width, 2))
            return cv2.cvtColor(uyvy, cv2.COLOR_YUV2RGB_UYVY)
        raise ValueError(f"unsupported image encoding: {msg.encoding}")

    def _image_rows(self, msg: Image, min_step: int) -> np.ndarray:
        height = int(msg.height)
        step = int(msg.step) if int(msg.step) > 0 else min_step
        data = np.frombuffer(msg.data, dtype=np.uint8)
        if step < min_step and data.size == height * min_step:
            step = min_step
        if step < min_step:
            raise ValueError(f"invalid image step: {step} < {min_step}")
        required = height * step
        if data.size < required and data.size == height * min_step:
            step = min_step
            required = height * step
        if data.size < required:
            raise ValueError(f"image data too short: {data.size} < {required}")
        return data[:required].reshape((height, step))

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

        white_mask = cv2.inRange(hsv, self.white_hsv_low, self.white_hsv_high)
        yellow_mask = cv2.inRange(hsv, self.yellow_hsv_low, self.yellow_hsv_high)
        mask = cv2.bitwise_or(white_mask, yellow_mask)

        roi = np.zeros((height, width), dtype=np.uint8)
        roi_top = int(np.clip(self.roi_top_ratio, 0.0, 1.0) * height)
        roi_bottom = int(np.clip(self.roi_bottom_ratio, 0.0, 1.0) * height)
        left_bottom = int(np.clip(self.roi_left_bottom_ratio, 0.0, 1.0) * width)
        left_top = int(np.clip(self.roi_left_top_ratio, 0.0, 1.0) * width)
        right_top = int(np.clip(self.roi_right_top_ratio, 0.0, 1.0) * width)
        right_bottom = int(np.clip(self.roi_right_bottom_ratio, 0.0, 1.0) * width)
        polygon = np.array(
            [
                [
                    (left_bottom, roi_bottom),
                    (left_top, roi_top),
                    (right_top, roi_top),
                    (right_bottom, roi_bottom),
                ]
            ],
            dtype=np.int32,
        )
        cv2.fillPoly(roi, polygon, 255)
        mask = cv2.bitwise_and(mask, roi)

        kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT, (self.morph_kernel_size, self.morph_kernel_size)
        )
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        return (mask > 0).astype(np.uint8)

    def _mask_to_path(self, mask: np.ndarray, image_msg: Image) -> tuple[Path, LaneFitDebug]:
        height, width = mask.shape[:2]
        roi_top = int(np.clip(self.roi_top_ratio, 0.0, 1.0) * height)
        roi_bottom = int(np.clip(self.roi_bottom_ratio, 0.0, 1.0) * height)
        if roi_bottom <= roi_top:
            roi_top = int(0.45 * height)
            roi_bottom = int(0.98 * height)

        path = Path()
        path.header.stamp = image_msg.header.stamp
        path.header.frame_id = self.output_frame or image_msg.header.frame_id or "base_link"
        debug = LaneFitDebug(mask_pixels=int(np.count_nonzero(mask)))

        ys = np.linspace(roi_bottom - 1, roi_top, max(2, self.path_points)).astype(np.int32)
        image_center = 0.5 * float(width)
        left_points: list[tuple[float, float]] = []
        right_points: list[tuple[float, float]] = []
        lane_widths_m: list[float] = []
        for y in ys:
            band_half = max(2, height // 120)
            y0 = max(0, y - band_half)
            y1 = min(height, y + band_half + 1)
            xs = np.where(mask[y0:y1, :] > 0)[1]
            if xs.size < self.min_mask_pixels_per_band:
                continue

            left = xs[xs < image_center]
            right = xs[xs >= image_center]
            forward = self._row_to_forward_m(y, roi_top, roi_bottom)
            meters_per_px = self._meters_per_pixel(width, forward)
            if left.size and right.size:
                debug.both_band_count += 1
            if left.size:
                left_edge = float(np.percentile(left, 85))
                lateral = (left_edge - image_center) * meters_per_px
                left_points.append((forward, lateral))
                debug.left_band_count += 1
                debug.left_pixels.append((int(round(left_edge)), int(y)))
            if right.size:
                right_edge = float(np.percentile(right, 15))
                lateral = (right_edge - image_center) * meters_per_px
                right_points.append((forward, lateral))
                debug.right_band_count += 1
                debug.right_pixels.append((int(round(right_edge)), int(y)))
            if left.size and right.size:
                lane_widths_m.append(max(0.0, (right_edge - left_edge) * meters_per_px))

        if lane_widths_m:
            debug.observed_lane_width_m = float(np.median(lane_widths_m))

        center_laterals = self._fit_center_laterals(left_points, right_points, debug)
        if center_laterals is None:
            self.smoothed_laterals = None
            return path, debug

        forward_samples = np.linspace(
            self.path_forward_min_m,
            self.path_forward_max_m,
            max(2, self.path_points),
            dtype=np.float32,
        )
        center_laterals = np.clip(
            center_laterals,
            -self.max_abs_lateral_m,
            self.max_abs_lateral_m,
        )
        if debug.confidence >= self.min_lane_confidence:
            center_laterals, debug.smoothed = self._smooth_laterals(
                center_laterals, debug.confidence
            )
        else:
            self.smoothed_laterals = None

        for forward, lateral in zip(forward_samples, center_laterals):
            pose = PoseStamped()
            pose.header = path.header
            pose.pose.position.x = float(forward)
            pose.pose.position.y = float(lateral)
            pose.pose.position.z = 0.0
            pose.pose.orientation.w = 1.0
            path.poses.append(pose)

        path.poses.sort(key=lambda pose: pose.pose.position.x)
        return path, debug

    def _fit_center_laterals(
        self,
        left_points: list[tuple[float, float]],
        right_points: list[tuple[float, float]],
        debug: LaneFitDebug,
    ) -> Optional[np.ndarray]:
        forward_samples = np.linspace(
            self.path_forward_min_m,
            self.path_forward_max_m,
            max(2, self.path_points),
            dtype=np.float32,
        )
        left_fit = self._fit_side_lateral(left_points)
        right_fit = self._fit_side_lateral(right_points)
        if left_fit is None and right_fit is None:
            debug.reason = "insufficient_line_points"
            return None

        if left_fit is not None:
            left_lateral = np.polyval(left_fit, forward_samples)
        else:
            left_lateral = None
        if right_fit is not None:
            right_lateral = np.polyval(right_fit, forward_samples)
        else:
            right_lateral = None

        if left_lateral is not None and right_lateral is not None:
            center_lateral = 0.5 * (left_lateral + right_lateral)
            side_score = 1.0
        elif left_lateral is not None:
            center_lateral = left_lateral + 0.5 * self.assumed_lane_width_m
            side_score = 0.65
        else:
            center_lateral = right_lateral - 0.5 * self.assumed_lane_width_m
            side_score = 0.65

        total_bands = max(1, len(left_points) + len(right_points))
        coverage_score = min(1.0, total_bands / max(1.0, 2.0 * float(self.path_points)))
        width_score = 1.0
        if debug.observed_lane_width_m is not None:
            if debug.observed_lane_width_m < self.min_lane_width_m:
                width_score = max(
                    0.25,
                    debug.observed_lane_width_m / max(self.min_lane_width_m, 1.0e-6),
                )
            elif debug.observed_lane_width_m > self.max_lane_width_m:
                width_score = max(
                    0.25,
                    self.max_lane_width_m / max(debug.observed_lane_width_m, 1.0e-6),
                )
        debug.confidence = max(0.0, min(1.0, coverage_score * side_score * width_score))
        if debug.confidence < self.min_lane_confidence:
            debug.reason = "low_lane_confidence"
        return center_lateral.astype(np.float32)

    def _fit_side_lateral(self, points: list[tuple[float, float]]) -> Optional[np.ndarray]:
        if len(points) < self.min_fit_points_per_side:
            return None
        xs = np.asarray([point[0] for point in points], dtype=np.float32)
        ys = np.asarray([point[1] for point in points], dtype=np.float32)
        degree = min(2, len(points) - 1)
        try:
            return np.polyfit(xs, ys, degree)
        except (TypeError, ValueError, np.linalg.LinAlgError):
            return None

    def _smooth_laterals(
        self, lateral: np.ndarray, confidence: float
    ) -> tuple[np.ndarray, bool]:
        if self.smoothing_alpha <= 0.0:
            self.smoothed_laterals = lateral
            return lateral, False
        if self.smoothed_laterals is None or self.smoothed_laterals.shape != lateral.shape:
            self.smoothed_laterals = lateral
            return lateral, False
        jump_m = float(np.max(np.abs(lateral - self.smoothed_laterals)))
        if jump_m > self.max_smoothing_jump_m:
            self.smoothed_laterals = lateral
            return lateral, False
        alpha = max(0.05, min(1.0, self.smoothing_alpha * (0.5 + 0.5 * confidence)))
        smoothed = alpha * lateral + (1.0 - alpha) * self.smoothed_laterals
        self.smoothed_laterals = smoothed.astype(np.float32)
        return self.smoothed_laterals, True

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

    def _forward_to_row(self, forward_m: float, roi_top: int, roi_bottom: int) -> int:
        span = max(1.0, self.path_forward_max_m - self.path_forward_min_m)
        ratio = np.clip((forward_m - self.path_forward_min_m) / span, 0.0, 1.0)
        return int(round(float(roi_bottom) - ratio * float(roi_bottom - roi_top)))

    def _publish_debug_images(
        self,
        image_msg: Image,
        rgb: np.ndarray,
        mask: np.ndarray,
        path: Path,
        debug: LaneFitDebug,
    ) -> None:
        if self.debug_mask_pub is not None:
            mask_msg = Image()
            mask_msg.header = image_msg.header
            mask_msg.height = int(mask.shape[0])
            mask_msg.width = int(mask.shape[1])
            mask_msg.encoding = "mono8"
            mask_msg.is_bigendian = 0
            mask_msg.step = int(mask_msg.width)
            mask_msg.data = (mask.astype(np.uint8) * 255).tobytes()
            self.debug_mask_pub.publish(mask_msg)

        if self.debug_image_pub is None:
            return
        overlay = rgb.copy()
        mask_pixels = mask > 0
        if np.any(mask_pixels):
            lane_color = np.asarray([255, 220, 40], dtype=np.uint8)
            overlay[mask_pixels] = (
                0.45 * overlay[mask_pixels].astype(np.float32)
                + 0.55 * lane_color.astype(np.float32)
            ).astype(np.uint8)

        height, width = mask.shape[:2]
        roi_top = int(np.clip(self.roi_top_ratio, 0.0, 1.0) * height)
        roi_bottom = int(np.clip(self.roi_bottom_ratio, 0.0, 1.0) * height)
        image_center = 0.5 * float(width)
        left_bottom = int(np.clip(self.roi_left_bottom_ratio, 0.0, 1.0) * width)
        left_top = int(np.clip(self.roi_left_top_ratio, 0.0, 1.0) * width)
        right_top = int(np.clip(self.roi_right_top_ratio, 0.0, 1.0) * width)
        right_bottom = int(np.clip(self.roi_right_bottom_ratio, 0.0, 1.0) * width)
        roi_poly = np.array(
            [[(left_bottom, roi_bottom), (left_top, roi_top), (right_top, roi_top), (right_bottom, roi_bottom)]],
            dtype=np.int32,
        )
        cv2.polylines(overlay, roi_poly, True, (90, 170, 255), 2)
        for point in debug.left_pixels:
            cv2.circle(overlay, point, 4, (80, 220, 255), -1)
        for point in debug.right_pixels:
            cv2.circle(overlay, point, 4, (255, 140, 90), -1)

        path_pixels = []
        for pose in path.poses:
            forward = float(pose.pose.position.x)
            lateral = float(pose.pose.position.y)
            row = self._forward_to_row(forward, roi_top, roi_bottom)
            meters_per_px = self._meters_per_pixel(width, forward)
            col = int(round(image_center + lateral / max(meters_per_px, 1.0e-6)))
            if 0 <= row < height and 0 <= col < width:
                path_pixels.append((col, row))
        if len(path_pixels) >= 2:
            cv2.polylines(overlay, [np.asarray(path_pixels, dtype=np.int32)], False, (40, 255, 120), 3)
        for point in path_pixels:
            cv2.circle(overlay, point, 3, (210, 255, 220), -1)

        text = f"lane conf={debug.confidence:.2f} L={debug.left_band_count} R={debug.right_band_count}"
        cv2.putText(
            overlay,
            text,
            (12, 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        overlay_msg = Image()
        overlay_msg.header = image_msg.header
        overlay_msg.height = int(overlay.shape[0])
        overlay_msg.width = int(overlay.shape[1])
        overlay_msg.encoding = "rgb8"
        overlay_msg.is_bigendian = 0
        overlay_msg.step = int(overlay_msg.width) * 3
        overlay_msg.data = overlay.tobytes()
        self.debug_image_pub.publish(overlay_msg)

    def _publish_status(
        self,
        image_msg: Optional[Image],
        *,
        published: bool,
        reason: str,
        path: Optional[Path] = None,
        debug: Optional[LaneFitDebug] = None,
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
            "confidence": self.last_lane_confidence if debug is None else debug.confidence,
            "min_lane_confidence": self.min_lane_confidence,
            "left_band_count": 0 if debug is None else debug.left_band_count,
            "right_band_count": 0 if debug is None else debug.right_band_count,
            "both_band_count": 0 if debug is None else debug.both_band_count,
            "mask_pixels": 0 if debug is None else debug.mask_pixels,
            "observed_lane_width_m": None if debug is None else debug.observed_lane_width_m,
            "smoothed": False if debug is None else debug.smoothed,
            "publish_debug_images": self.publish_debug_images,
            "debug_mask_topic": self.debug_mask_topic if self.publish_debug_images else "",
            "debug_image_topic": self.debug_image_topic if self.publish_debug_images else "",
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
