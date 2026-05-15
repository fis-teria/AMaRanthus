import json
from typing import Optional

from PyQt5.QtWidgets import QFrame, QGridLayout, QLabel

from .models import ShadowMetrics
from .rich_widgets import GaugeWidget, MetricBar


class ShadowMetricsPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)

        layout = QGridLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(8)

        title = QLabel("Shadow Mode")
        title.setObjectName("PanelTitle")
        layout.addWidget(title, 0, 0, 1, 2)

        self.ego_speed_gauge = GaugeWidget("EGO SPEED", "m/s", 0.0, 35.0)
        self.yaw_rate_bar = MetricBar("Yaw rate", "rad/s", 0.0, 1.0)
        self.ego_curvature_bar = MetricBar("Ego curvature", "1/m", 0.0, 0.12)
        self.driver_steering_bar = MetricBar("Driver steering", "rad", 0.0, 0.7)
        self.virtual_steering_bar = MetricBar("Virtual steering", "rad", 0.0, 0.7)
        self.steering_delta_bar = MetricBar("Steering delta", "rad", 0.0, 0.7)
        self.curvature_delta_bar = MetricBar("Curvature delta", "1/m", 0.0, 0.12)
        self.warning_bar = MetricBar("Warning score", "", 0.0, 1.0)
        self.intervention_bar = MetricBar("Intervention score", "", 0.0, 1.0)
        self.summary_label = QLabel("--")
        self.summary_label.setObjectName("SummaryLabel")
        self.summary_label.setWordWrap(True)

        layout.addWidget(self.ego_speed_gauge, 1, 0, 3, 1)
        layout.addWidget(self.yaw_rate_bar, 1, 1)
        layout.addWidget(self.ego_curvature_bar, 2, 1)
        layout.addWidget(self.driver_steering_bar, 3, 1)
        layout.addWidget(self.virtual_steering_bar, 4, 0)
        layout.addWidget(self.steering_delta_bar, 4, 1)
        layout.addWidget(self.curvature_delta_bar, 5, 0)
        layout.addWidget(self.warning_bar, 5, 1)
        layout.addWidget(self.intervention_bar, 6, 0)
        layout.addWidget(self.summary_label, 6, 1)

    def update_metrics(self, metrics: ShadowMetrics) -> None:
        ego_speed = metrics.ego_speed_mps
        self.ego_speed_gauge.set_value(
            ego_speed,
            "--" if ego_speed is None else f"{ego_speed * 3.6:.1f} km/h",
        )
        self.yaw_rate_bar.set_metric(
            self._abs_value(metrics.ego_yaw_rate_radps),
            self._format_unit(metrics.ego_yaw_rate_radps, "rad/s", 3),
            "left/right rotation magnitude",
        )
        self.ego_curvature_bar.set_metric(
            self._abs_value(metrics.ego_curvature_inv_m),
            self._format_unit(metrics.ego_curvature_inv_m, "1/m", 4),
            "path bend estimate",
        )
        self.driver_steering_bar.set_metric(
            self._abs_value(metrics.driver_steering_proxy_rad),
            self._format_unit(metrics.driver_steering_proxy_rad, "rad", 3),
            "driver proxy",
        )
        self.virtual_steering_bar.set_metric(
            self._abs_value(metrics.virtual_steering_rad),
            self._format_unit(metrics.virtual_steering_rad, "rad", 3),
            "planner proxy",
        )
        self.steering_delta_bar.set_metric(
            self._abs_value(metrics.steering_delta_rad),
            self._format_unit(metrics.steering_delta_rad, "rad", 3),
            "driver vs virtual",
        )
        self.curvature_delta_bar.set_metric(
            self._abs_value(metrics.curvature_delta_inv_m),
            self._format_unit(metrics.curvature_delta_inv_m, "1/m", 4),
            "trajectory disagreement",
        )
        self.warning_bar.set_metric(
            metrics.virtual_warning_score,
            self._format_score(metrics.virtual_warning_score),
            self._score_caption(metrics.virtual_warning_score),
        )
        self.intervention_bar.set_metric(
            metrics.intervention_score,
            self._format_score(metrics.intervention_score),
            self._score_caption(metrics.intervention_score),
        )
        self.summary_label.setText(self._format_summary(metrics.summary))

    def _format_speed(self, value_mps: Optional[float]) -> str:
        if value_mps is None:
            return "--"
        return f"{value_mps:.2f} m/s ({value_mps * 3.6:.1f} km/h)"

    def _format_unit(self, value: Optional[float], unit: str, precision: int) -> str:
        if value is None:
            return "--"
        return f"{value:.{precision}f} {unit}"

    def _format_score(self, value: Optional[float]) -> str:
        if value is None:
            return "--"
        return f"{value:.2f}"

    def _abs_value(self, value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        return abs(value)

    def _score_caption(self, value: Optional[float]) -> str:
        if value is None:
            return "waiting"
        if value >= 0.7:
            return "high attention"
        if value >= 0.35:
            return "watch"
        return "nominal"

    def _format_summary(self, value: str) -> str:
        if not value or value == "--":
            return "--"

        try:
            payload = json.loads(value)
        except json.JSONDecodeError:
            return self._truncate(value)

        if not isinstance(payload, dict):
            return value

        valid = payload.get("valid")
        if valid is False:
            reason = str(payload.get("reason", "invalid"))
            age = payload.get("max_observed_age_sec")
            if isinstance(age, (int, float)):
                return f"invalid: {reason} / age {age:.2f}s"
            return f"invalid: {reason}"

        age = payload.get("max_observed_age_sec")
        if isinstance(age, (int, float)):
            return f"valid / age {age:.2f}s"
        return "valid" if valid is True else self._truncate(value)

    def _truncate(self, value: str, limit: int = 96) -> str:
        if len(value) <= limit:
            return value
        return value[: limit - 3] + "..."
