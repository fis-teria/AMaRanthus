#!/usr/bin/env python3
import copy
import json
import math
from dataclasses import dataclass
from typing import Optional

import rclpy
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Odometry, Path
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import NavSatFix, NavSatStatus
from std_msgs.msg import String


EARTH_M_PER_DEG = 111_320.0


def stamp_to_float(stamp) -> float:
    return float(stamp.sec) + float(stamp.nanosec) * 1.0e-9


def finite(value: float) -> bool:
    return math.isfinite(float(value))


@dataclass
class FixSample:
    source: str
    msg: NavSatFix
    received_sec: float
    accuracy_m: float
    weight: float


@dataclass
class LocalFix:
    source: str
    x: float
    y: float
    z: float
    accuracy_m: float
    age_sec: float
    weight: float


class ShadowLocalizationFusionNode(Node):
    def __init__(self):
        super().__init__("shadow_localization_fusion")

        self.lidar_odom_topic = self.declare_parameter("lidar_odom_topic", "/Odometry").value
        self.phone_fix_topic = self.declare_parameter("phone_fix_topic", "/phone/gps/fix").value
        self.spresense_fix_topic = self.declare_parameter(
            "spresense_fix_topic", "/spresense/gps/fix"
        ).value
        self.fused_odom_topic = self.declare_parameter(
            "fused_odom_topic", "/shadow/fused/odometry"
        ).value
        self.fused_path_topic = self.declare_parameter(
            "fused_path_topic", "/shadow/fused/path"
        ).value
        self.status_topic = self.declare_parameter("status_topic", "/shadow/fused/status").value
        self.output_frame = self.declare_parameter("output_frame", "").value
        self.child_frame_id = self.declare_parameter("child_frame_id", "").value
        self.fix_timeout_sec = float(self.declare_parameter("fix_timeout_sec", 3.0).value)
        self.max_fix_accuracy_m = float(
            self.declare_parameter("max_fix_accuracy_m", 25.0).value
        )
        self.unknown_accuracy_m = float(
            self.declare_parameter("unknown_accuracy_m", 15.0).value
        )
        self.min_fix_interval_sec = float(
            self.declare_parameter("min_fix_interval_sec", 0.2).value
        )
        self.phone_weight = float(self.declare_parameter("phone_weight", 0.6).value)
        self.spresense_weight = float(self.declare_parameter("spresense_weight", 1.0).value)
        self.correction_gain = self.clamp(
            float(self.declare_parameter("correction_gain", 0.08).value), 0.0, 1.0
        )
        self.max_correction_step_m = max(
            0.01, float(self.declare_parameter("max_correction_step_m", 0.5).value)
        )
        self.max_residual_m = max(
            1.0, float(self.declare_parameter("max_residual_m", 40.0).value)
        )
        self.apply_z_correction = bool(
            self.declare_parameter("apply_z_correction", False).value
        )
        self.path_buffer_size = max(
            1, int(self.declare_parameter("path_buffer_size", 200).value)
        )

        self.origin_lat: Optional[float] = None
        self.origin_lon: Optional[float] = None
        self.origin_alt: float = 0.0
        self.gnss_to_odom_offset = None
        self.correction = [0.0, 0.0, 0.0]
        self.last_lidar_odom: Optional[Odometry] = None
        self.last_fixes: dict[str, FixSample] = {}
        self.last_fix_received_by_topic: dict[str, float] = {}
        self.path = Path()
        self.last_status = {}

        self.odom_pub = self.create_publisher(Odometry, self.fused_odom_topic, 10)
        self.path_pub = self.create_publisher(Path, self.fused_path_topic, 10)
        self.status_pub = self.create_publisher(String, self.status_topic, 10)

        self.subscriptions_ = [
            self.create_subscription(
                Odometry, self.lidar_odom_topic, self.odom_callback, qos_profile_sensor_data
            ),
            self.create_subscription(
                NavSatFix,
                self.phone_fix_topic,
                lambda msg: self.fix_callback("phone", msg, self.phone_weight),
                qos_profile_sensor_data,
            ),
            self.create_subscription(
                NavSatFix,
                self.spresense_fix_topic,
                lambda msg: self.fix_callback("spresense", msg, self.spresense_weight),
                qos_profile_sensor_data,
            ),
        ]

        self.get_logger().info(
            "shadow_localization_fusion started "
            f"lidar_odom={self.lidar_odom_topic} "
            f"phone_fix={self.phone_fix_topic} "
            f"spresense_fix={self.spresense_fix_topic} "
            f"output={self.fused_odom_topic}"
        )

    @staticmethod
    def clamp(value: float, low: float, high: float) -> float:
        return min(high, max(low, value))

    def now_sec(self) -> float:
        return stamp_to_float(self.get_clock().now().to_msg())

    def fix_callback(self, source: str, msg: NavSatFix, base_weight: float) -> None:
        now_sec = self.now_sec()
        last_received = self.last_fix_received_by_topic.get(source)
        if (
            last_received is not None
            and now_sec - last_received < self.min_fix_interval_sec
        ):
            return
        self.last_fix_received_by_topic[source] = now_sec

        accuracy = self.fix_accuracy_m(msg)
        if not self.fix_usable(msg, accuracy):
            self.last_status[f"{source}_reject_reason"] = self.reject_reason(msg, accuracy)
            return

        self.last_fixes[source] = FixSample(
            source=source,
            msg=msg,
            received_sec=now_sec,
            accuracy_m=accuracy,
            weight=max(0.0, base_weight),
        )
        self.ensure_origin(msg)

    def odom_callback(self, msg: Odometry) -> None:
        self.last_lidar_odom = msg
        now_sec = self.now_sec()
        local_fixes = self.fresh_local_fixes(now_sec)
        correction_target = self.weighted_correction_target(msg, local_fixes)
        correction_applied = False

        if correction_target is not None:
            self.update_correction(correction_target)
            correction_applied = True

        fused = copy.deepcopy(msg)
        fused.header.frame_id = self.output_frame or msg.header.frame_id
        fused.child_frame_id = self.child_frame_id or msg.child_frame_id
        fused.pose.pose.position.x = msg.pose.pose.position.x + self.correction[0]
        fused.pose.pose.position.y = msg.pose.pose.position.y + self.correction[1]
        if self.apply_z_correction:
            fused.pose.pose.position.z = msg.pose.pose.position.z + self.correction[2]

        self.inflate_pose_covariance(fused, local_fixes)
        self.odom_pub.publish(fused)
        self.publish_path(fused)
        self.publish_status(now_sec, local_fixes, correction_target, correction_applied)

    def fix_usable(self, msg: NavSatFix, accuracy_m: float) -> bool:
        if msg.status.status < NavSatStatus.STATUS_FIX:
            return False
        if not (finite(msg.latitude) and finite(msg.longitude)):
            return False
        if accuracy_m > self.max_fix_accuracy_m:
            return False
        return True

    def reject_reason(self, msg: NavSatFix, accuracy_m: float) -> str:
        if msg.status.status < NavSatStatus.STATUS_FIX:
            return "no_fix"
        if not (finite(msg.latitude) and finite(msg.longitude)):
            return "invalid_lat_lon"
        if accuracy_m > self.max_fix_accuracy_m:
            return f"accuracy>{self.max_fix_accuracy_m:.1f}m"
        return "unknown"

    def fix_accuracy_m(self, msg: NavSatFix) -> float:
        if msg.position_covariance_type != NavSatFix.COVARIANCE_TYPE_UNKNOWN:
            variances = [
                value
                for value in (msg.position_covariance[0], msg.position_covariance[4])
                if finite(value) and value >= 0.0
            ]
            if variances:
                return math.sqrt(max(variances))
        return self.unknown_accuracy_m

    def ensure_origin(self, msg: NavSatFix) -> None:
        if self.origin_lat is not None:
            return
        self.origin_lat = float(msg.latitude)
        self.origin_lon = float(msg.longitude)
        self.origin_alt = float(msg.altitude) if finite(msg.altitude) else 0.0
        self.get_logger().info(
            "GNSS origin initialized "
            f"lat={self.origin_lat:.8f} lon={self.origin_lon:.8f}"
        )

    def fresh_local_fixes(self, now_sec: float) -> list[LocalFix]:
        local_fixes = []
        for sample in self.last_fixes.values():
            age = now_sec - sample.received_sec
            if age > self.fix_timeout_sec:
                continue
            local = self.fix_to_local(sample)
            if local is not None:
                local_fixes.append(
                    LocalFix(
                        source=sample.source,
                        x=local[0],
                        y=local[1],
                        z=local[2],
                        accuracy_m=sample.accuracy_m,
                        age_sec=age,
                        weight=sample.weight,
                    )
                )
        return local_fixes

    def fix_to_local(self, sample: FixSample):
        if self.origin_lat is None or self.origin_lon is None:
            return None

        lat = float(sample.msg.latitude)
        lon = float(sample.msg.longitude)
        alt = float(sample.msg.altitude) if finite(sample.msg.altitude) else self.origin_alt
        mean_lat = math.radians((lat + self.origin_lat) * 0.5)
        north_m = (lat - self.origin_lat) * EARTH_M_PER_DEG
        east_m = (lon - self.origin_lon) * EARTH_M_PER_DEG * math.cos(mean_lat)
        up_m = alt - self.origin_alt

        if self.gnss_to_odom_offset is None and self.last_lidar_odom is not None:
            odom_pos = self.last_lidar_odom.pose.pose.position
            self.gnss_to_odom_offset = [
                float(odom_pos.x) - east_m,
                float(odom_pos.y) - north_m,
                float(odom_pos.z) - up_m,
            ]
            self.get_logger().info(
                "GNSS local frame aligned to LiDAR odometry "
                f"offset=({self.gnss_to_odom_offset[0]:.2f}, "
                f"{self.gnss_to_odom_offset[1]:.2f}, {self.gnss_to_odom_offset[2]:.2f})"
            )

        if self.gnss_to_odom_offset is None:
            return None

        return (
            east_m + self.gnss_to_odom_offset[0],
            north_m + self.gnss_to_odom_offset[1],
            up_m + self.gnss_to_odom_offset[2],
        )

    def weighted_correction_target(self, odom: Odometry, fixes: list[LocalFix]):
        if not fixes:
            return None

        ox = float(odom.pose.pose.position.x)
        oy = float(odom.pose.pose.position.y)
        oz = float(odom.pose.pose.position.z)
        weighted = [0.0, 0.0, 0.0]
        total_weight = 0.0

        for fix in fixes:
            residual = [fix.x - ox, fix.y - oy, fix.z - oz]
            residual_norm = math.hypot(residual[0], residual[1])
            if residual_norm > self.max_residual_m:
                self.last_status[f"{fix.source}_reject_reason"] = (
                    f"residual>{self.max_residual_m:.1f}m"
                )
                continue
            accuracy_weight = 1.0 / max(1.0, fix.accuracy_m * fix.accuracy_m)
            age_weight = max(0.0, 1.0 - fix.age_sec / max(0.001, self.fix_timeout_sec))
            weight = fix.weight * accuracy_weight * max(0.1, age_weight)
            weighted[0] += residual[0] * weight
            weighted[1] += residual[1] * weight
            weighted[2] += residual[2] * weight
            total_weight += weight

        if total_weight <= 0.0:
            return None
        return [value / total_weight for value in weighted]

    def update_correction(self, target) -> None:
        desired_step = [
            (target[0] - self.correction[0]) * self.correction_gain,
            (target[1] - self.correction[1]) * self.correction_gain,
            (target[2] - self.correction[2]) * self.correction_gain,
        ]
        xy_norm = math.hypot(desired_step[0], desired_step[1])
        if xy_norm > self.max_correction_step_m:
            scale = self.max_correction_step_m / xy_norm
            desired_step[0] *= scale
            desired_step[1] *= scale
        self.correction[0] += desired_step[0]
        self.correction[1] += desired_step[1]
        if self.apply_z_correction:
            self.correction[2] += self.clamp(
                desired_step[2], -self.max_correction_step_m, self.max_correction_step_m
            )

    def inflate_pose_covariance(self, fused: Odometry, fixes: list[LocalFix]) -> None:
        if not fixes:
            return
        best_accuracy = min(fix.accuracy_m for fix in fixes)
        variance = max(0.0, best_accuracy * best_accuracy)
        existing_x = fused.pose.covariance[0]
        existing_y = fused.pose.covariance[7]
        if not finite(existing_x) or existing_x <= 0.0:
            fused.pose.covariance[0] = variance
        if not finite(existing_y) or existing_y <= 0.0:
            fused.pose.covariance[7] = variance

    def publish_path(self, fused: Odometry) -> None:
        self.path.header = fused.header
        pose = PoseStamped()
        pose.header = fused.header
        pose.pose = fused.pose.pose
        self.path.poses.append(pose)
        while len(self.path.poses) > self.path_buffer_size:
            self.path.poses.pop(0)
        self.path_pub.publish(self.path)

    def publish_status(
        self,
        now_sec: float,
        fixes: list[LocalFix],
        correction_target,
        correction_applied: bool,
    ) -> None:
        fix_status = {}
        for source in ("phone", "spresense"):
            sample = self.last_fixes.get(source)
            if sample is None:
                fix_status[source] = {"available": False}
                continue
            age = now_sec - sample.received_sec
            fix_status[source] = {
                "available": True,
                "fresh": age <= self.fix_timeout_sec,
                "age_sec": age,
                "accuracy_m": sample.accuracy_m,
                "weight": sample.weight,
            }

        status = {
            "stamp": now_sec,
            "lidar_odom_topic": self.lidar_odom_topic,
            "fused_odom_topic": self.fused_odom_topic,
            "origin_ready": self.origin_lat is not None,
            "gnss_aligned": self.gnss_to_odom_offset is not None,
            "fresh_sources": [fix.source for fix in fixes],
            "correction_applied": correction_applied,
            "correction_m": {
                "x": self.correction[0],
                "y": self.correction[1],
                "z": self.correction[2],
            },
            "correction_target_m": None
            if correction_target is None
            else {
                "x": correction_target[0],
                "y": correction_target[1],
                "z": correction_target[2],
            },
            "fixes": fix_status,
        }
        for key, value in self.last_status.items():
            status[key] = value
        self.status_pub.publish(String(data=json.dumps(status, sort_keys=True)))


def main(args=None):
    rclpy.init(args=args)
    node = ShadowLocalizationFusionNode()
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
