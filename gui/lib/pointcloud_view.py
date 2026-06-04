from typing import List

from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPolygonF
from PyQt5.QtWidgets import QSizePolicy, QWidget

from .models import PointCloudPoint


class PointCloudView(QWidget):
    def __init__(
        self,
        parent=None,
        *,
        fixed_range_m: float = 80.0,
        fixed_z_min_m: float = -3.0,
        fixed_z_max_m: float = 3.0,
    ):
        super().__init__(parent)
        self.setMinimumSize(500, 500)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)
        self.points: List[PointCloudPoint] = []
        self.route_pointcloud_points: List[PointCloudPoint] = []
        self.route_path_points: List[PointCloudPoint] = []
        self.e2e_path_points: List[PointCloudPoint] = []
        self.max_range_m = max(5.0, float(fixed_range_m))
        self.z_min_m = float(fixed_z_min_m)
        self.z_max_m = float(fixed_z_max_m)
        if self.z_max_m - self.z_min_m < 0.1:
            self.z_min_m -= 0.05
            self.z_max_m += 0.05
        self.yaw_rad = 0.0
        self.pitch_rad = 0.72
        self.zoom = 1.0
        self._last_mouse_pos = None
        self._projection_basis = None

    def set_points(self, points: List[PointCloudPoint]) -> None:
        if points is self.points:
            return
        self.points = points
        self.update()

    def set_route_layers(
        self,
        *,
        route_pointcloud_points: List[PointCloudPoint],
        route_path_points: List[PointCloudPoint],
        e2e_path_points: List[PointCloudPoint],
    ) -> None:
        if (
            route_pointcloud_points is self.route_pointcloud_points
            and route_path_points is self.route_path_points
            and e2e_path_points is self.e2e_path_points
        ):
            return
        self.route_pointcloud_points = route_pointcloud_points
        self.route_path_points = route_path_points
        self.e2e_path_points = e2e_path_points
        self.update()

    def _world_point(self, point: PointCloudPoint) -> tuple[float, float, float]:
        return -point.y_m, point.x_m, point.z_m

    def _camera_basis(self):
        import math

        target = (0.0, min(self.max_range_m * 0.18, 12.0), 0.0)
        distance = max(8.0, self.max_range_m * 1.55 * self.zoom)
        cos_pitch = math.cos(self.pitch_rad)
        camera = (
            target[0] + distance * math.sin(self.yaw_rad) * cos_pitch,
            target[1] - distance * math.cos(self.yaw_rad) * cos_pitch,
            target[2] + distance * math.sin(self.pitch_rad),
        )

        forward = self._normalize(
            (
                target[0] - camera[0],
                target[1] - camera[1],
                target[2] - camera[2],
            )
        )
        right = self._normalize(self._cross(forward, (0.0, 0.0, 1.0)))
        up = self._cross(right, forward)
        return camera, right, up, forward

    def _project(self, point: tuple[float, float, float]) -> tuple[QPointF, float] | None:
        basis = self._projection_basis or self._camera_basis()
        camera, right, up, forward = basis
        relative = (
            point[0] - camera[0],
            point[1] - camera[1],
            point[2] - camera[2],
        )
        depth = self._dot(relative, forward)
        if depth <= 0.15:
            return None

        focal_px = min(self.width(), self.height()) * 0.95
        view_x = self._dot(relative, right)
        view_y = self._dot(relative, up)
        screen_x = self.width() * 0.5 + view_x * focal_px / depth
        screen_y = self.height() * 0.58 - view_y * focal_px / depth
        return QPointF(screen_x, screen_y), depth

    def _dot(self, a, b) -> float:
        return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

    def _cross(self, a, b):
        return (
            a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0],
        )

    def _normalize(self, vector):
        import math

        length = math.sqrt(self._dot(vector, vector))
        if length <= 1e-9:
            return 0.0, 0.0, 0.0
        return vector[0] / length, vector[1] / length, vector[2] / length

    def _height_color(self, z_m: float) -> QColor:
        ratio = (z_m - self.z_min_m) / (self.z_max_m - self.z_min_m)
        ratio = max(0.0, min(1.0, ratio))
        if ratio < 0.5:
            t = ratio * 2.0
            r = int(40 + 20 * t)
            g = int(170 + 70 * t)
            b = int(255 - 90 * t)
        else:
            t = (ratio - 0.5) * 2.0
            r = int(60 + 195 * t)
            g = int(240 - 70 * t)
            b = int(165 - 120 * t)
        return QColor(r, g, b, 210)

    def draw_background(self, painter: QPainter) -> None:
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(15, 17, 20))

        grid_pen = QPen(QColor(55, 65, 75))
        grid_pen.setWidth(1)
        painter.setPen(grid_pen)

        step = 5
        limit = int(self.max_range_m // step) * step
        for value in range(-limit, limit + step, step):
            self._draw_world_line(painter, (value, -limit, 0.0), (value, limit, 0.0))
            self._draw_world_line(painter, (-limit, value, 0.0), (limit, value, 0.0))

        self._draw_axis(painter, (18, 160, 255), (0.0, 0.0, 0.0), (0.0, self.max_range_m, 0.0))
        self._draw_axis(painter, (255, 170, 70), (0.0, 0.0, 0.0), (self.max_range_m * 0.35, 0.0, 0.0))
        self._draw_axis(painter, (90, 235, 140), (0.0, 0.0, 0.0), (0.0, 0.0, 3.0))

        painter.restore()

    def _draw_world_line(
        self,
        painter: QPainter,
        start: tuple[float, float, float],
        end: tuple[float, float, float],
    ) -> None:
        projected_start = self._project(start)
        projected_end = self._project(end)
        if projected_start is None or projected_end is None:
            return
        painter.drawLine(projected_start[0], projected_end[0])

    def _draw_axis(
        self,
        painter: QPainter,
        rgb: tuple[int, int, int],
        start: tuple[float, float, float],
        end: tuple[float, float, float],
    ) -> None:
        axis_pen = QPen(QColor(*rgb))
        axis_pen.setWidth(3)
        painter.setPen(axis_pen)
        self._draw_world_line(painter, start, end)

    def draw_vehicle(self, painter: QPainter) -> None:
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        vertices = [
            (0.0, 2.2, 0.25),
            (-0.85, -1.6, 0.2),
            (0.85, -1.6, 0.2),
        ]
        projected = [self._project(vertex) for vertex in vertices]
        if any(item is None for item in projected):
            painter.restore()
            return

        body = QPolygonF([item[0] for item in projected if item is not None])
        painter.setBrush(QBrush(QColor(230, 245, 255)))
        painter.setPen(QPen(QColor(90, 145, 255), 2))
        painter.drawPolygon(body)
        painter.restore()

    def draw_points(self, painter: QPainter) -> None:
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, False)
        for point in self.points:
            projected = self._project(self._world_point(point))
            if projected is None:
                continue
            view_point, depth = projected
            size = max(2, min(5, int(120.0 / max(depth, 1.0))))
            painter.setPen(QPen(self._height_color(point.z_m), size))
            painter.drawPoint(view_point)
        painter.restore()

    def draw_route_pointcloud(self, painter: QPainter) -> None:
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, False)
        pen = QPen(QColor(255, 214, 80, 230), 4)
        painter.setPen(pen)
        for point in self.route_pointcloud_points:
            projected = self._project(self._world_point(point))
            if projected is None:
                continue
            painter.drawPoint(projected[0])
        painter.restore()

    def draw_path_layer(
        self,
        painter: QPainter,
        points: List[PointCloudPoint],
        *,
        line_color: QColor,
        point_color: QColor,
        width: int,
    ) -> None:
        if not points:
            return

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        line_pen = QPen(line_color, width)
        line_pen.setCapStyle(Qt.RoundCap)
        line_pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(line_pen)

        previous = None
        projected_points = []
        for point in points:
            projected = self._project(self._world_point(point))
            if projected is None:
                previous = None
                continue
            view_point = projected[0]
            projected_points.append(view_point)
            if previous is not None:
                painter.drawLine(previous, view_point)
            previous = view_point

        painter.setBrush(QBrush(point_color))
        painter.setPen(QPen(point_color, max(2, width - 1)))
        for view_point in projected_points:
            painter.drawPoint(view_point)

        painter.restore()

    def draw_route_layers(self, painter: QPainter) -> None:
        self.draw_route_pointcloud(painter)
        self.draw_path_layer(
            painter,
            self.route_path_points,
            line_color=QColor(90, 235, 140, 230),
            point_color=QColor(185, 255, 210, 235),
            width=4,
        )
        self.draw_path_layer(
            painter,
            self.e2e_path_points,
            line_color=QColor(60, 205, 255, 240),
            point_color=QColor(210, 246, 255, 245),
            width=5,
        )

    def draw_overlay(self, painter: QPainter) -> None:
        painter.save()
        painter.setPen(QColor(232, 238, 245))

        jp_font = QFont()
        jp_font.setFamily("Noto Sans CJK JP, IPAGothic, TakaoGothic, Yu Gothic, MS Gothic, Arial")
        jp_font.setPointSize(11)
        painter.setFont(jp_font)

        painter.drawText(12, 24, "PointCloud 3D view")
        painter.drawText(12, 46, f"points: {len(self.points)}")
        painter.drawText(12, 68, f"route cloud: {len(self.route_pointcloud_points)}")
        painter.drawText(12, 90, f"route path: {len(self.route_path_points)}")
        painter.drawText(12, 112, f"e2e path: {len(self.e2e_path_points)}")
        painter.drawText(12, 134, f"range: +/-{self.max_range_m:.0f} m")
        painter.drawText(12, 156, f"height: {self.z_min_m:.2f}m - {self.z_max_m:.2f}m")
        painter.restore()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._last_mouse_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._last_mouse_pos is None or not event.buttons() & Qt.LeftButton:
            super().mouseMoveEvent(event)
            return

        delta = event.pos() - self._last_mouse_pos
        self._last_mouse_pos = event.pos()
        self.yaw_rad += delta.x() * 0.008
        self.pitch_rad = max(0.18, min(1.35, self.pitch_rad + delta.y() * 0.006))
        self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._last_mouse_pos = None
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta > 0:
            self.zoom *= 0.88
        elif delta < 0:
            self.zoom *= 1.12
        self.zoom = max(0.35, min(3.5, self.zoom))
        self.update()
        super().wheelEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        self._projection_basis = self._camera_basis()
        self.draw_background(painter)
        self.draw_points(painter)
        self.draw_route_layers(painter)
        self.draw_vehicle(painter)
        self.draw_overlay(painter)
        self._projection_basis = None
