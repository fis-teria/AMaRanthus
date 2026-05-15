import json
from typing import Optional

from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QFrame, QGridLayout, QLabel

from .models import ShadowMetrics


class ShadowMetricsPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)

        layout = QGridLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setHorizontalSpacing(14)
        layout.setVerticalSpacing(8)

        jp_font = QFont()
        jp_font.setFamily("Noto Sans CJK JP, IPAGothic, TakaoGothic, Yu Gothic, MS Gothic, Arial")
        jp_font.setPointSize(9)

        title = QLabel("Shadow Mode")
        title.setFont(jp_font)
        title.setStyleSheet("font-weight: bold; font-size: 15px;")
        layout.addWidget(title, 0, 0, 1, 2)

        self.labels = {}
        items = [
            ("Ego速度", "--"),
            ("Yaw rate", "--"),
            ("Ego曲率", "--"),
            ("ドライバ操舵", "--"),
            ("仮想操舵", "--"),
            ("仮想曲率", "--"),
            ("操舵差分", "--"),
            ("曲率差分", "--"),
            ("警告スコア", "--"),
            ("介入スコア", "--"),
            ("Summary", "--"),
        ]

        for row, (title_text, value) in enumerate(items, start=1):
            title_label = QLabel(title_text)
            value_label = QLabel(value)
            title_label.setFont(jp_font)
            value_label.setFont(jp_font)
            title_label.setStyleSheet("font-weight: bold;")
            value_label.setStyleSheet("font-size: 14px;")
            value_label.setWordWrap(True)
            layout.addWidget(title_label, row, 0)
            layout.addWidget(value_label, row, 1)
            self.labels[title_text] = value_label

    def update_metrics(self, metrics: ShadowMetrics) -> None:
        self.labels["Ego速度"].setText(self._format_speed(metrics.ego_speed_mps))
        self.labels["Yaw rate"].setText(
            self._format_unit(metrics.ego_yaw_rate_radps, "rad/s", 3)
        )
        self.labels["Ego曲率"].setText(self._format_unit(metrics.ego_curvature_inv_m, "1/m", 4))
        self.labels["ドライバ操舵"].setText(
            self._format_unit(metrics.driver_steering_proxy_rad, "rad", 3)
        )
        self.labels["仮想操舵"].setText(self._format_unit(metrics.virtual_steering_rad, "rad", 3))
        self.labels["仮想曲率"].setText(self._format_unit(metrics.virtual_curvature_inv_m, "1/m", 4))
        self.labels["操舵差分"].setText(self._format_unit(metrics.steering_delta_rad, "rad", 3))
        self.labels["曲率差分"].setText(self._format_unit(metrics.curvature_delta_inv_m, "1/m", 4))
        self.labels["警告スコア"].setText(self._format_score(metrics.virtual_warning_score))
        self.labels["介入スコア"].setText(self._format_score(metrics.intervention_score))
        self.labels["Summary"].setText(self._format_summary(metrics.summary))

        self._apply_score_style("警告スコア", metrics.virtual_warning_score)
        self._apply_score_style("介入スコア", metrics.intervention_score)

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

    def _apply_score_style(self, label_name: str, value: Optional[float]) -> None:
        label = self.labels[label_name]
        if value is None:
            label.setStyleSheet("font-size: 14px;")
            return

        if value >= 0.7:
            color = "#b42318"
        elif value >= 0.35:
            color = "#b54708"
        else:
            color = "#027a48"

        label.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {color};")
