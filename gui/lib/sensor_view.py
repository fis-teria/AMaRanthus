from typing import List

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPolygonF
from PyQt5.QtWidgets import QSizePolicy, QWidget

from .models import DetectedObject
from .ui_config import UiRenderConfig


class SensorView(QWidget):
    def __init__(self, render_config: UiRenderConfig, parent=None):
        super().__init__(parent)
        self.setMinimumSize(500, 500)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.render_config = render_config
        self.max_range_m = render_config.max_range_m
        self.scan_points: List[QPointF] = []
        self.lane_points: List[QPointF] = []
        self.objects: List[DetectedObject] = []
        self.speed_kmh = 0.0
        self.min_distance_m = 99.0

    def _current_max_range_m(self) -> float:
        if not self.render_config.dynamic_range_enabled:
            return self.render_config.max_range_m

        speed_min = self.render_config.dynamic_range_speed_min_kmh
        speed_max = self.render_config.dynamic_range_speed_max_kmh
        range_min = self.render_config.dynamic_range_min_m
        range_max = self.render_config.dynamic_range_max_m

        if speed_max <= speed_min:
            return range_max

        speed = max(speed_min, min(self.speed_kmh, speed_max))
        ratio = (speed - speed_min) / (speed_max - speed_min)
        return range_min + (range_max - range_min) * ratio

    def set_data(
        self,
        scan_xy_m: List[QPointF],
        lane_xy_m: List[QPointF],
        objects: List[DetectedObject],
        speed_kmh: float,
        min_distance_m: float,
    ) -> None:
        self.scan_points = scan_xy_m
        self.lane_points = lane_xy_m
        self.objects = objects
        self.speed_kmh = speed_kmh
        self.min_distance_m = min_distance_m
        self.max_range_m = self._current_max_range_m()
        self.update()

    def meter_to_view(self, x_m: float, y_m: float) -> QPointF:
        w = self.width()
        h = self.height()
        origin_x = w * 0.5
        origin_y = h * 0.82
        scale = min(w * 0.42, h * 0.72) / self.max_range_m
        px = origin_x + x_m * scale
        py = origin_y - y_m * scale
        return QPointF(px, py)

    def draw_grid(self, painter: QPainter) -> None:
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        jp_font = QFont()
        jp_font.setFamily("Noto Sans CJK JP, IPAGothic, TakaoGothic, Yu Gothic, MS Gothic, Arial")
        painter.setFont(jp_font)

        painter.fillRect(self.rect(), QColor(18, 18, 22))

        pen = QPen(QColor(70, 70, 80))
        pen.setWidth(1)
        painter.setPen(pen)

        for dist in [5, 10, 15, 20]:
            center = self.meter_to_view(0.0, 0.0)
            edge = self.meter_to_view(dist, 0.0)
            radius = abs(edge.x() - center.x())
            rect = QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2)
            painter.drawEllipse(rect)

        axis_pen = QPen(QColor(90, 120, 255))
        axis_pen.setWidth(2)
        painter.setPen(axis_pen)
        p0 = self.meter_to_view(0.0, 0.0)
        p1 = self.meter_to_view(0.0, self.max_range_m)
        painter.drawLine(p0, p1)

        side_pen = QPen(QColor(70, 70, 90))
        side_pen.setWidth(1)
        painter.setPen(side_pen)
        left = self.meter_to_view(-self.max_range_m, 0.0)
        right = self.meter_to_view(self.max_range_m, 0.0)
        painter.drawLine(left, right)

        danger_brush = QBrush(QColor(255, 80, 80, 40))
        painter.setBrush(danger_brush)
        painter.setPen(Qt.NoPen)

        origin = self.meter_to_view(0.0, 0.0)
        left_edge = self.meter_to_view(-1.8, 6.0)
        right_edge = self.meter_to_view(1.8, 6.0)
        painter.drawPolygon(QPolygonF([origin, left_edge, right_edge]))
        painter.restore()

    def draw_vehicle(self, painter: QPainter) -> None:
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        center = self.meter_to_view(0.0, 0.0)
        body = QPolygonF(
            [
                QPointF(center.x(), center.y() - 18),
                QPointF(center.x() - 14, center.y() + 16),
                QPointF(center.x() + 14, center.y() + 16),
            ]
        )

        painter.setBrush(QBrush(QColor(80, 200, 255)))
        painter.setPen(QPen(QColor(220, 240, 255), 2))
        painter.drawPolygon(body)
        painter.restore()

    def draw_scan(self, painter: QPainter) -> None:
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(0, 180, 255, 180))
        pen.setWidth(self.render_config.scan_point_size)
        painter.setPen(pen)

        for point_m in self.scan_points:
            painter.drawPoint(self.meter_to_view(point_m.x(), point_m.y()))

        painter.restore()

    def draw_lane(self, painter: QPainter) -> None:
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        lane_pen = QPen(QColor(255, 220, 80))
        lane_pen.setWidth(self.render_config.lane_point_size)
        painter.setPen(lane_pen)

        for point_m in self.lane_points:
            painter.drawPoint(self.meter_to_view(point_m.x(), point_m.y()))

        painter.restore()

    def draw_objects(self, painter: QPainter) -> None:
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        for obj in self.objects:
            point = self.meter_to_view(obj.x_m, obj.y_m)

            if obj.kind == "obstacle":
                painter.setBrush(QBrush(QColor(255, 96, 96)))
                painter.setPen(QPen(QColor(255, 230, 230), 2))
                rect = QRectF(
                    point.x() - self.render_config.obstacle_marker_width_px / 2.0,
                    point.y() - self.render_config.obstacle_marker_height_px / 2.0,
                    self.render_config.obstacle_marker_width_px,
                    self.render_config.obstacle_marker_height_px,
                )
                painter.drawRect(rect)
                painter.drawText(
                    point
                    + QPointF(
                        self.render_config.obstacle_label_dx_px,
                        self.render_config.obstacle_label_dy_px,
                    ),
                    "Obstacle",
                )
            else:
                painter.setBrush(QBrush(QColor(255, 170, 40)))
                painter.setPen(QPen(QColor(255, 240, 210), 2))
                painter.drawEllipse(point, 8, 8)
                painter.drawText(point + QPointF(10, -10), obj.kind)

        painter.restore()

    def draw_overlay_text(self, painter: QPainter) -> None:
        painter.save()
        painter.setPen(QColor(230, 230, 230))

        jp_font = QFont()
        jp_font.setFamily("Noto Sans CJK JP, IPAGothic, TakaoGothic, Yu Gothic, MS Gothic, Arial")
        jp_font.setPointSize(11)
        painter.setFont(jp_font)

        painter.drawText(12, 24, "右画面: 周辺 LaserScan / Lane / Obstacle ビュー")
        painter.drawText(12, 46, f"表示レンジ: {self.max_range_m:.0f} m")
        painter.drawText(12, 68, f"最短距離: {self.min_distance_m:.2f} m")
        painter.drawText(12, 90, "青: 周辺状況  黄: lane / road edge  赤: obstacle")
        painter.restore()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        self.draw_grid(painter)
        self.draw_scan(painter)
        self.draw_lane(painter)
        self.draw_objects(painter)
        self.draw_vehicle(painter)
        self.draw_overlay_text(painter)
