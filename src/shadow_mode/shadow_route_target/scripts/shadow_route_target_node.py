#!/usr/bin/env python3
import json
import math
from dataclasses import dataclass
from typing import Optional

import rclpy
from geometry_msgs.msg import PointStamped
from nav_msgs.msg import Path
from rclpy.node import Node
from std_msgs.msg import String


@dataclass
class PathSample:
    msg: Optional[Path] = None
    received_sec: Optional[float] = None


class ShadowRouteTargetNode(Node):
    def __init__(self) -> None:
        super().__init__("shadow_route_target")

        self.output_topic = self.declare_parameter(
            "output_topic", "/shadow/route/target_point"
        ).value
        self.status_topic = self.declare_parameter(
            "status_topic", "/shadow/route/target_status"
        ).value
        self.route_command_topic = self.declare_parameter(
            "route_command_topic", "/shadow/route/command"
        ).value
        self.publish_route_command = bool(
            self.declare_parameter("publish_route_command", True).value
        )
        self.route_command = self.declare_parameter("route_command", "lane_follow").value
        self.publish_rate_hz = float(self.declare_parameter("publish_rate_hz", 10.0).value)
        self.input_timeout_sec = float(
            self.declare_parameter("input_timeout_sec", 0.5).value
        )
        self.lookahead_distance_m = float(
            self.declare_parameter("lookahead_distance_m", 15.0).value
        )
        self.min_forward_distance_m = float(
            self.declare_parameter("min_forward_distance_m", 1.0).value
        )
        self.source_priority = self._parse_priority(
            self.declare_parameter(
                "source_priority", "gui_route,image_lane,shadow_virtual"
            ).value
        )
        self.gui_route_path_topic = self.declare_parameter(
            "gui_route_path_topic", "/shadow/route/gui_path"
        ).value
        self.image_lane_path_topic = self.declare_parameter(
            "image_lane_path_topic", "/shadow/perception/lane_path"
        ).value
        self.shadow_virtual_path_topic = self.declare_parameter(
            "shadow_virtual_path_topic", "/shadow/virtual/path"
        ).value
        self.default_frame_id = self.declare_parameter("default_frame_id", "base_link").value
        self.default_target_x_m = float(
            self.declare_parameter("default_target_x_m", 15.0).value
        )
        self.default_target_y_m = float(
            self.declare_parameter("default_target_y_m", 0.0).value
        )
        self.publish_default_when_missing = bool(
            self.declare_parameter("publish_default_when_missing", False).value
        )

        self.samples = {
            "gui_route": PathSample(),
            "image_lane": PathSample(),
            "shadow_virtual": PathSample(),
        }

        self.create_subscription(Path, self.gui_route_path_topic, self._on_gui_route, 10)
        self.create_subscription(Path, self.image_lane_path_topic, self._on_image_lane, 10)
        self.create_subscription(Path, self.shadow_virtual_path_topic, self._on_shadow_path, 10)

        self.target_pub = self.create_publisher(PointStamped, self.output_topic, 10)
        self.status_pub = self.create_publisher(String, self.status_topic, 10)
        self.command_pub = (
            self.create_publisher(String, self.route_command_topic, 10)
            if self.publish_route_command
            else None
        )

        period = 1.0 / max(0.1, self.publish_rate_hz)
        self.timer = self.create_timer(period, self._on_timer)

        self.get_logger().info(
            "shadow_route_target started "
            f"output={self.output_topic} priority={','.join(self.source_priority)}"
        )

    @staticmethod
    def _parse_priority(value) -> list[str]:
        if isinstance(value, (list, tuple)):
            items = [str(item).strip() for item in value]
        else:
            items = [item.strip() for item in str(value).split(",")]
        valid = {"gui_route", "image_lane", "shadow_virtual"}
        parsed = [item for item in items if item in valid]
        return parsed or ["gui_route", "image_lane", "shadow_virtual"]

    def _now_sec(self) -> float:
        return self.get_clock().now().nanoseconds * 1e-9

    def _on_gui_route(self, msg: Path) -> None:
        self.samples["gui_route"] = PathSample(msg=msg, received_sec=self._now_sec())

    def _on_image_lane(self, msg: Path) -> None:
        self.samples["image_lane"] = PathSample(msg=msg, received_sec=self._now_sec())

    def _on_shadow_path(self, msg: Path) -> None:
        self.samples["shadow_virtual"] = PathSample(msg=msg, received_sec=self._now_sec())

    def _fresh_sample(self, name: str, now_sec: float) -> Optional[Path]:
        sample = self.samples[name]
        if sample.msg is None or sample.received_sec is None:
            return None
        if now_sec - sample.received_sec > self.input_timeout_sec:
            return None
        return sample.msg

    def _select_target_from_path(self, path: Path) -> Optional[tuple[float, float, float, str, int]]:
        previous_x = 0.0
        previous_y = 0.0
        distance_m = 0.0
        last_candidate = None

        for index, pose_stamped in enumerate(path.poses):
            point = pose_stamped.pose.position
            x = float(point.x)
            y = float(point.y)
            z = float(point.z)
            if not all(math.isfinite(value) for value in (x, y, z)):
                continue
            if x < self.min_forward_distance_m:
                continue

            distance_m += math.hypot(x - previous_x, y - previous_y)
            frame_id = pose_stamped.header.frame_id or path.header.frame_id or self.default_frame_id
            last_candidate = (x, y, z, frame_id, index)
            if distance_m >= self.lookahead_distance_m:
                return last_candidate
            previous_x = x
            previous_y = y

        return last_candidate

    def _build_target(self, source: str, selected: tuple[float, float, float, str, int]) -> PointStamped:
        x, y, z, frame_id, _ = selected
        msg = PointStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = frame_id
        msg.point.x = x
        msg.point.y = y
        msg.point.z = z
        return msg

    def _build_default_target(self) -> PointStamped:
        msg = PointStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self.default_frame_id
        msg.point.x = self.default_target_x_m
        msg.point.y = self.default_target_y_m
        msg.point.z = 0.0
        return msg

    def _publish_status(
        self,
        *,
        active_source: str,
        selected_index: Optional[int],
        published: bool,
        target: Optional[PointStamped],
        now_sec: float,
    ) -> None:
        source_status = {}
        for name, sample in self.samples.items():
            age = None if sample.received_sec is None else now_sec - sample.received_sec
            source_status[name] = {
                "age_sec": age,
                "fresh": age is not None and age <= self.input_timeout_sec,
                "poses": 0 if sample.msg is None else len(sample.msg.poses),
            }

        payload = {
            "active_source": active_source,
            "published": published,
            "selected_index": selected_index,
            "lookahead_distance_m": self.lookahead_distance_m,
            "source_priority": self.source_priority,
            "sources": source_status,
            "target": None,
        }
        if target is not None:
            payload["target"] = {
                "frame_id": target.header.frame_id,
                "x": target.point.x,
                "y": target.point.y,
                "z": target.point.z,
            }
        self.status_pub.publish(String(data=json.dumps(payload, sort_keys=True)))

    def _on_timer(self) -> None:
        now_sec = self._now_sec()
        active_source = ""
        selected_index = None
        target = None

        for source in self.source_priority:
            path = self._fresh_sample(source, now_sec)
            if path is None:
                continue
            selected = self._select_target_from_path(path)
            if selected is None:
                continue
            target = self._build_target(source, selected)
            active_source = source
            selected_index = selected[4]
            break

        if target is None and self.publish_default_when_missing:
            target = self._build_default_target()
            active_source = "default"

        published = target is not None
        if target is not None:
            self.target_pub.publish(target)
            if self.command_pub is not None:
                self.command_pub.publish(String(data=str(self.route_command)))

        self._publish_status(
            active_source=active_source,
            selected_index=selected_index,
            published=published,
            target=target,
            now_sec=now_sec,
        )


def main() -> None:
    rclpy.init()
    node = ShadowRouteTargetNode()
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
