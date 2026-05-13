#!/usr/bin/env python3
import json
import math
from pathlib import Path
import sys

_SOURCE_ROOT = Path(__file__).resolve().parents[1]
if (_SOURCE_ROOT / "shadow_mode_e2e_metrics").exists():
    sys.path.insert(0, str(_SOURCE_ROOT))

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32, String


class Signal:
    def __init__(self):
        self.value = None
        self.received_at = None

    def update(self, value, stamp):
        self.value = float(value)
        self.received_at = stamp

    def fresh(self, now, timeout_sec):
        if self.received_at is None:
            return False
        return (now - self.received_at).nanoseconds * 1.0e-9 <= timeout_sec

    def age_sec(self, now):
        if self.received_at is None:
            return None
        return max(0.0, (now - self.received_at).nanoseconds * 1.0e-9)


class ShadowModeE2EMetricsNode(Node):
    def __init__(self):
        super().__init__("shadow_mode_e2e_metrics")

        self.ego_speed_topic = self.declare_parameter("ego_speed_topic", "/shadow/ego/speed").value
        self.ego_curvature_topic = self.declare_parameter(
            "ego_curvature_topic", "/shadow/ego/curvature"
        ).value
        self.virtual_steering_topic = self.declare_parameter(
            "virtual_steering_topic", "/shadow/virtual/steering_proxy"
        ).value
        self.virtual_curvature_topic = self.declare_parameter(
            "virtual_curvature_topic", "/shadow/virtual/curvature"
        ).value
        self.e2e_steering_topic = self.declare_parameter(
            "e2e_steering_topic", "/shadow/e2e/steering_proxy"
        ).value
        self.e2e_curvature_topic = self.declare_parameter(
            "e2e_curvature_topic", "/shadow/e2e/curvature"
        ).value
        self.e2e_confidence_topic = self.declare_parameter(
            "e2e_confidence_topic", "/shadow/e2e/confidence"
        ).value
        self.publish_rate_hz = float(self.declare_parameter("publish_rate_hz", 10.0).value)
        self.input_timeout_sec = float(self.declare_parameter("input_timeout_sec", 0.5).value)
        self.wheel_base_m = float(self.declare_parameter("wheel_base_m", 2.7).value)
        self.steering_delta_scale_rad = float(
            self.declare_parameter("steering_delta_scale_rad", 0.35).value
        )
        self.curvature_delta_scale = float(
            self.declare_parameter("curvature_delta_scale", 0.08).value
        )
        self.confidence_penalty_weight = float(
            self.declare_parameter("confidence_penalty_weight", 0.25).value
        )

        self.signals = {
            "ego_speed": Signal(),
            "ego_curvature": Signal(),
            "virtual_steering": Signal(),
            "virtual_curvature": Signal(),
            "e2e_steering": Signal(),
            "e2e_curvature": Signal(),
            "e2e_confidence": Signal(),
        }

        self.subscriptions_ = [
            self.create_subscription(
                Float32,
                self.ego_speed_topic,
                lambda msg: self.update_signal("ego_speed", msg),
                10,
            ),
            self.create_subscription(
                Float32,
                self.ego_curvature_topic,
                lambda msg: self.update_signal("ego_curvature", msg),
                10,
            ),
            self.create_subscription(
                Float32,
                self.virtual_steering_topic,
                lambda msg: self.update_signal("virtual_steering", msg),
                10,
            ),
            self.create_subscription(
                Float32,
                self.virtual_curvature_topic,
                lambda msg: self.update_signal("virtual_curvature", msg),
                10,
            ),
            self.create_subscription(
                Float32,
                self.e2e_steering_topic,
                lambda msg: self.update_signal("e2e_steering", msg),
                10,
            ),
            self.create_subscription(
                Float32,
                self.e2e_curvature_topic,
                lambda msg: self.update_signal("e2e_curvature", msg),
                10,
            ),
            self.create_subscription(
                Float32,
                self.e2e_confidence_topic,
                lambda msg: self.update_signal("e2e_confidence", msg),
                10,
            ),
        ]

        self.e2e_steering_delta_pub = self.create_publisher(
            Float32, "/shadow/metrics/e2e_steering_delta", 10
        )
        self.e2e_virtual_steering_delta_pub = self.create_publisher(
            Float32, "/shadow/metrics/e2e_virtual_steering_delta", 10
        )
        self.e2e_curvature_delta_pub = self.create_publisher(
            Float32, "/shadow/metrics/e2e_curvature_delta", 10
        )
        self.e2e_intervention_score_pub = self.create_publisher(
            Float32, "/shadow/metrics/e2e_intervention_score", 10
        )
        self.summary_pub = self.create_publisher(String, "/shadow/metrics/e2e_summary", 10)

        self.timer = self.create_timer(
            1.0 / max(0.1, self.publish_rate_hz), self.timer_callback
        )
        self.get_logger().info("shadow_mode_e2e_metrics started")

    def update_signal(self, name, msg):
        self.signals[name].update(msg.data, self.get_clock().now())

    def missing_inputs(self, now):
        return [
            name
            for name, signal in self.signals.items()
            if not signal.fresh(now, self.input_timeout_sec)
        ]

    def timer_callback(self):
        now = self.get_clock().now()
        missing = self.missing_inputs(now)
        if missing:
            self.publish_summary(now, False, missing)
            return

        ego_curvature = self.signals["ego_curvature"].value
        virtual_steering = self.signals["virtual_steering"].value
        virtual_curvature = self.signals["virtual_curvature"].value
        e2e_steering = self.signals["e2e_steering"].value
        e2e_curvature = self.signals["e2e_curvature"].value
        e2e_confidence = max(0.0, min(1.0, self.signals["e2e_confidence"].value))

        driver_steering_proxy = math.atan(self.wheel_base_m * ego_curvature)
        e2e_steering_delta = e2e_steering - driver_steering_proxy
        e2e_virtual_steering_delta = e2e_steering - virtual_steering
        e2e_curvature_delta = e2e_curvature - ego_curvature
        e2e_virtual_curvature_delta = e2e_curvature - virtual_curvature

        steering_component = min(
            1.0, abs(e2e_steering_delta) / max(1.0e-6, self.steering_delta_scale_rad)
        )
        curvature_component = min(
            1.0, abs(e2e_curvature_delta) / max(1.0e-6, self.curvature_delta_scale)
        )
        confidence_component = (1.0 - e2e_confidence) * self.confidence_penalty_weight
        intervention_score = max(
            0.0,
            min(1.0, 0.45 * steering_component + 0.35 * curvature_component + confidence_component),
        )

        self.e2e_steering_delta_pub.publish(Float32(data=float(e2e_steering_delta)))
        self.e2e_virtual_steering_delta_pub.publish(
            Float32(data=float(e2e_virtual_steering_delta))
        )
        self.e2e_curvature_delta_pub.publish(Float32(data=float(e2e_curvature_delta)))
        self.e2e_intervention_score_pub.publish(Float32(data=float(intervention_score)))
        self.publish_summary(
            now,
            True,
            [],
            {
                "driver_steering_proxy": driver_steering_proxy,
                "e2e_steering_delta": e2e_steering_delta,
                "e2e_virtual_steering_delta": e2e_virtual_steering_delta,
                "e2e_curvature_delta": e2e_curvature_delta,
                "e2e_virtual_curvature_delta": e2e_virtual_curvature_delta,
                "e2e_intervention_score": intervention_score,
                "e2e_confidence": e2e_confidence,
            },
        )

    def publish_summary(self, now, valid, missing, values=None):
        ages = {
            name: signal.age_sec(now)
            for name, signal in self.signals.items()
            if signal.age_sec(now) is not None
        }
        payload = {
            "stamp": float(now.nanoseconds) * 1.0e-9,
            "valid": valid,
            "missing_inputs": missing,
            "input_age_sec": ages,
        }
        if values:
            payload.update(values)
        self.summary_pub.publish(String(data=json.dumps(payload, sort_keys=True)))


def main(args=None):
    rclpy.init(args=args)
    node = ShadowModeE2EMetricsNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    sys.exit(main())
