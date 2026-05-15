from typing import Optional

from PyQt5.QtCore import QRect, Qt
from PyQt5.QtGui import QColor, QFont, QImage, QPainter, QPen
from PyQt5.QtWidgets import QSizePolicy, QWidget

from .models import CameraFrame


class CameraView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(500, 500)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._frame: Optional[CameraFrame] = None

    def set_frame(self, frame: Optional[CameraFrame]) -> None:
        self._frame = frame
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(12, 14, 18))

        if self._frame is None or self._frame.image.isNull():
            self._draw_waiting(painter)
            return

        image = self._frame.image
        target = self._scaled_rect(image)
        painter.drawImage(target, image)
        self._draw_overlay(painter, target)

    def _scaled_rect(self, image: QImage) -> QRect:
        image_size = image.size()
        image_size.scale(self.size(), Qt.KeepAspectRatio)
        x = (self.width() - image_size.width()) // 2
        y = (self.height() - image_size.height()) // 2
        return QRect(x, y, image_size.width(), image_size.height())

    def _draw_waiting(self, painter: QPainter) -> None:
        painter.save()
        painter.setPen(QColor(230, 236, 244))
        font = QFont()
        font.setPointSize(15)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignCenter, "Camera waiting")
        painter.restore()

    def _draw_overlay(self, painter: QPainter, target: QRect) -> None:
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(235, 240, 248), 1))
        painter.fillRect(0, 0, self.width(), 76, QColor(0, 0, 0, 150))

        font = QFont()
        font.setPointSize(11)
        painter.setFont(font)
        frame = self._frame
        if frame is not None:
            painter.drawText(12, 24, f"Camera: {frame.topic}")
            painter.drawText(
                12,
                48,
                f"{frame.width}x{frame.height} {frame.encoding} frame={frame.frame_id or '--'}",
            )

        painter.setPen(QPen(QColor(90, 170, 255), 2))
        painter.drawRect(target.adjusted(0, 0, -1, -1))
        painter.restore()
