#!/usr/bin/env python3
import json
import math
from dataclasses import dataclass
from typing import Optional

import rclpy
from geometry_msgs.msg import PointStamped, PoseStamped
from nav_msgs.msg import Odometry, Path
from rclpy.node import Node
from std_msgs.msg import String


@dataclass
class PathSample:
    msg: Optional[Path] = None
    received_sec: Optional[float] = None


@dataclass
class TargetSelection:
    x: float
    y: float
    z: float
    frame_id: str
    index: int
    requested_distance_m: float
    actual_distance_m: float
    reached: bool


class ShadowRouteTargetNode(Node):
    def __init__(self) -> None:
        super().__init__("shadow_route_target")

        self.output_topic = self.declare_parameter(
            "output_topic", "/shadow/route/target_point"
        ).value
        self.output_path_topic = self.declare_parameter(
            "output_path_topic", "/shadow/route/target_path"
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
        self.speed_adaptive_lookahead = bool(
            self.declare_parameter("speed_adaptive_lookahead", True).value
        )
        self.lookahead_time_sec = max(
            0.0, float(self.declare_parameter("lookahead_time_sec", 1.2).value)
        )
        self.max_lookahead_distance_m = max(
            self.lookahead_distance_m,
            float(self.declare_parameter("max_lookahead_distance_m", 60.0).value),
        )
        self.min_forward_distance_m = float(
            self.declare_parameter("min_forward_distance_m", 1.0).value
        )
        self.odom_topic = self.declare_parameter("odom_topic", "/Odometry").value
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
        self.odom_msg: Optional[Odometry] = None
        self.odom_received_sec: Optional[float] = None

        self.create_subscription(Path, self.gui_route_path_topic, self._on_gui_route, 10)
        self.create_subscription(Path, self.image_lane_path_topic, self._on_image_lane, 10)
        self.create_subscription(Path, self.shadow_virtual_path_topic, self._on_shadow_path, 10)
        self.create_subscription(Odometry, self.odom_topic, self._on_odom, 10)

        self.target_pub = self.create_publisher(PointStamped, self.output_topic, 10)
        self.path_pub = self.create_publisher(Path, self.output_path_topic, 10)
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

    def _on_odom(self, msg: Odometry) -> None:
        self.odom_msg = msg
        self.odom_received_sec = self._now_sec()

    def _fresh_sample(self, name: str, now_sec: float) -> Optional[Path]:
        sample = self.samples[name]
        if sample.msg is None or sample.received_sec is None:
            return None
        if now_sec - sample.received_sec > self.input_timeout_sec:
            return None
        return sample.msg

    def _select_target_from_path(
        self, path: Path, lookahead_distance_m: float
    ) -> Optional[TargetSelection]:
        previous_x = 0.0
        previous_y = 0.0
        distance_m = 0.0
        last_candidate = None
        last_distance_m = 0.0
        requested_distance_m = max(0.0, float(lookahead_distance_m))

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
            last_candidate = TargetSelection(
                x=x,
                y=y,
                z=z,
                frame_id=frame_id,
                index=index,
                requested_distance_m=requested_distance_m,
                actual_distance_m=distance_m,
                reached=False,
            )
            last_distance_m = distance_m
            if distance_m >= requested_distance_m:
                last_candidate.reached = True
                return last_candidate
            previous_x = x
            previous_y = y

        if last_candidate is not None:
            last_candidate.actual_distance_m = last_distance_m
        return last_candidate

    def _build_target(self, source: str, selected: TargetSelection) -> PointStamped:
        msg = PointStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = selected.frame_id
        msg.point.x = selected.x
        msg.point.y = selected.y
        msg.point.z = selected.z
        return msg

    def _build_default_target(self, lookahead_distance_m: float) -> PointStamped:
        msg = PointStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self.default_frame_id
        msg.point.x = max(self.default_target_x_m, float(lookahead_distance_m))
        msg.point.y = self.default_target_y_m
        msg.point.z = 0.0
        return msg

    def _build_default_path(self, lookahead_distance_m: float) -> Path:
        now = self.get_clock().now().to_msg()
        path = Path()
        path.header.stamp = now
        path.header.frame_id = self.default_frame_id
        lookahead_distance_m = max(self.min_forward_distance_m, float(lookahead_distance_m))
        forward_points = [
            max(self.min_forward_distance_m, lookahead_distance_m * 0.33),
            lookahead_distance_m,
            max(lookahead_distance_m + 1.0, lookahead_distance_m * 1.67),
        ]
        max_x = max(self.default_target_x_m, lookahead_distance_m, 1.0)
        for x in forward_points:
            pose = PoseStamped()
            pose.header.stamp = now
            pose.header.frame_id = self.default_frame_id
            pose.pose.position.x = float(x)
            pose.pose.position.y = self.default_target_y_m * min(1.0, float(x) / max_x)
            pose.pose.position.z = 0.0
            pose.pose.orientation.w = 1.0
            path.poses.append(pose)
        return path

    def _stamp_selected_path(self, path: Path, frame_id: str) -> Path:
        stamped = Path()
        stamped.header.stamp = self.get_clock().now().to_msg()
        stamped.header.frame_id = path.header.frame_id or frame_id or self.default_frame_id
        stamped.poses = list(path.poses)
        return stamped

    def _speed_status(self, now_sec: float) -> dict[str, Optional[float] | str | bool]:
        age_sec = None if self.odom_received_sec is None else max(0.0, now_sec - self.odom_received_sec)
        if self.odom_msg is None:
            return {"speed_mps": 0.0, "source": "missing", "age_sec": age_sec, "fresh": False}
        if age_sec is not None and age_sec > self.input_timeout_sec:
            return {"speed_mps": 0.0, "source": "stale_odom", "age_sec": age_sec, "fresh": False}
        twist = self.odom_msg.twist.twist.linear
        speed_mps = math.sqrt(twist.x * twist.x + twist.y * twist.y + twist.z * twist.z)
        return {"speed_mps": speed_mps, "source": "odom", "age_sec": age_sec, "fresh": True}

    def _requested_lookahead_distance(self, speed_mps: float) -> float:
        distance_m = self.lookahead_distance_m
        if self.speed_adaptive_lookahead:
            distance_m += max(0.0, float(speed_mps)) * self.lookahead_time_sec
        return min(self.max_lookahead_distance_m, max(self.lookahead_distance_m, distance_m))

    def _publish_status(
        self,
        *,
        active_source: str,
        selected_index: Optional[int],
        published: bool,
        published_path: bool,
        target: Optional[PointStamped],
        path: Optional[Path],
        selected: Optional[TargetSelection],
        speed_status: dict[str, Optional[float] | str | bool],
        requested_lookahead_distance_m: float,
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
            "requested_lookahead_distance_m": requested_lookahead_distance_m,
            "actual_lookahead_distance_m": (
                None if selected is None else selected.actual_distance_m
            ),
            "lookahead_reached": False if selected is None else selected.reached,
            "speed_mps": speed_status["speed_mps"],
            "speed_source": speed_status["source"],
            "speed_age_sec": speed_status["age_sec"],
            "speed_fresh": speed_status["fresh"],
            "speed_adaptive": {
                "enabled": self.speed_adaptive_lookahead,
                "lookahead_time_sec": self.lookahead_time_sec,
                "base_lookahead_distance_m": self.lookahead_distance_m,
                "max_lookahead_distance_m": self.max_lookahead_distance_m,
                "odom_topic": self.odom_topic,
            },
            "source_priority": self.source_priority,
            "sources": source_status,
            "output_path_topic": self.output_path_topic,
            "published_path": published_path,
            "path": None,
            "target": None,
        }
        if path is not None:
            payload["path"] = {
                "frame_id": path.header.frame_id,
                "poses": len(path.poses),
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
        speed_status = self._speed_status(now_sec)
        requested_lookahead_distance_m = self._requested_lookahead_distance(
            float(speed_status["speed_mps"])
        )
        active_source = ""
        selected_index = None
        target = None
        target_path = None
        selected = None

        for source in self.source_priority:
            path = self._fresh_sample(source, now_sec)
            if path is None:
                continue
            selected = self._select_target_from_path(path, requested_lookahead_distance_m)
            if selected is None:
                continue
            target = self._build_target(source, selected)
            target_path = self._stamp_selected_path(path, selected.frame_id)
            active_source = source
            selected_index = selected.index
            break

        if target is None and self.publish_default_when_missing:
            target = self._build_default_target(requested_lookahead_distance_m)
            target_path = self._build_default_path(requested_lookahead_distance_m)
            selected = TargetSelection(
                x=target.point.x,
                y=target.point.y,
                z=target.point.z,
                frame_id=target.header.frame_id,
                index=1,
                requested_distance_m=requested_lookahead_distance_m,
                actual_distance_m=requested_lookahead_distance_m,
                reached=True,
            )
            active_source = "default"

        published = target is not None
        if target is not None:
            self.target_pub.publish(target)
            if self.command_pub is not None:
                self.command_pub.publish(String(data=str(self.route_command)))
        published_path = target_path is not None
        if target_path is not None:
            self.path_pub.publish(target_path)

        self._publish_status(
            active_source=active_source,
            selected_index=selected_index,
            published=published,
            published_path=published_path,
            target=target,
            path=target_path,
            selected=selected,
            speed_status=speed_status,
            requested_lookahead_distance_m=requested_lookahead_distance_m,
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
