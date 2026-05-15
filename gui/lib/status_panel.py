from PyQt5.QtWidgets import QFrame, QGridLayout, QLabel

from .rich_widgets import GaugeWidget, MetricBar, StatusBadge, status_color
from .system_monitor import GpuStatus


class StatusPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)

        layout = QGridLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(8)

        title = QLabel("Vehicle Status")
        title.setObjectName("PanelTitle")
        layout.addWidget(title, 0, 0, 1, 2)

        self.speed_gauge = GaugeWidget("SPEED", "km/h", 0.0, 120.0)
        self.distance_bar = MetricBar("Forward clearance", "m", 0.0, 40.0, invert_color=True)
        self.obstacle_bar = MetricBar("Obstacle density", "", 0.0, 12.0)
        self.gpu_util_bar = MetricBar("GPU load", "%", 0.0, 100.0)
        self.gpu_memory_bar = MetricBar("GPU memory", "MiB", 0.0, 1.0)
        self.gpu_temp_bar = MetricBar("GPU temperature", "C", 20.0, 90.0)
        self.mode_badge = StatusBadge("MODE")
        self.gps_badge = StatusBadge("GPS")

        layout.addWidget(self.speed_gauge, 1, 0, 3, 1)
        layout.addWidget(self.distance_bar, 1, 1)
        layout.addWidget(self.obstacle_bar, 2, 1)
        layout.addWidget(self.mode_badge, 3, 1)
        layout.addWidget(self.gps_badge, 4, 0)
        layout.addWidget(self.gpu_util_bar, 4, 1)
        layout.addWidget(self.gpu_memory_bar, 5, 0)
        layout.addWidget(self.gpu_temp_bar, 5, 1)

        self.update_gpu_status(GpuStatus(available=False, error="waiting"))

    def update_status(
        self,
        speed_kmh: float,
        min_distance_m: float,
        obstacle_count: int,
        mode: str,
        gps_status: str,
    ) -> None:
        clearance_caption = self._clearance_caption(min_distance_m)
        self.speed_gauge.set_value(speed_kmh, clearance_caption)
        self.distance_bar.set_metric(
            min_distance_m,
            f"{min_distance_m:.2f} m",
            self._clearance_caption(min_distance_m),
        )
        self.obstacle_bar.set_metric(
            float(obstacle_count),
            str(obstacle_count),
            "0 sparse / 12+ dense",
        )
        self.mode_badge.set_status(
            mode,
            status_color(mode, ("auto", "autonomous", "drive"), ("manual", "standby", "stop")),
        )
        self.gps_badge.set_status(
            gps_status,
            status_color(gps_status, ("fix", "ok", "rtk"), ("lost", "none", "bad")),
        )

    def update_gpu_status(self, status: GpuStatus) -> None:
        if not status.available:
            detail = status.error or "GPU monitor unavailable"
            self.gpu_util_bar.set_metric(None, "--", detail)
            self.gpu_memory_bar.set_metric(None, "--", detail)
            self.gpu_temp_bar.set_metric(None, "--", detail)
            self.setToolTip(detail)
            return

        util = float(status.utilization_percent or 0)
        used = float(status.memory_used_mib or 0)
        total = float(status.memory_total_mib or 1)
        temp = float(status.temperature_c or 0)
        self.gpu_memory_bar.maximum = max(total, 1.0)
        self.gpu_util_bar.set_metric(util, f"{util:.0f}%", status.name)
        self.gpu_memory_bar.set_metric(
            used,
            f"{used:.0f}/{total:.0f} MiB",
            f"{(used / max(total, 1.0)) * 100.0:.0f}% used",
        )
        self.gpu_temp_bar.set_metric(temp, f"{temp:.0f} C", status.name)
        self.setToolTip(status.name)

    def _clearance_caption(self, distance_m: float) -> str:
        if distance_m < 5.0:
            return "critical clearance"
        if distance_m < 12.0:
            return "watch forward gap"
        return "clear forward path"
