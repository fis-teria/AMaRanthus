from typing import Optional

from PyQt5.QtCore import QRectF, QSize, Qt
from PyQt5.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPen
from PyQt5.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget


FONT_FAMILY = "Noto Sans CJK JP, IPAGothic, TakaoGothic, Yu Gothic, MS Gothic, Arial"


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


def level_color(ratio: float, invert: bool = False) -> QColor:
    value = 1.0 - ratio if invert else ratio
    if value >= 0.72:
        return QColor("#ef5b5b")
    if value >= 0.42:
        return QColor("#f6b94d")
    return QColor("#27c08a")


class GaugeWidget(QWidget):
    def __init__(
        self,
        title: str,
        unit: str,
        minimum: float = 0.0,
        maximum: float = 120.0,
        parent=None,
    ):
        super().__init__(parent)
        self.title = title
        self.unit = unit
        self.minimum = minimum
        self.maximum = maximum
        self.value: Optional[float] = None
        self.caption = "--"
        self.setMinimumSize(190, 150)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_value(self, value: Optional[float], caption: str | None = None) -> None:
        self.value = value
        self.caption = caption if caption is not None else "--"
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(220, 160)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(12, 8, -12, -8)
        painter.setPen(QPen(QColor("#2c3845"), 1))
        painter.setBrush(QColor("#141b22"))
        painter.drawRoundedRect(QRectF(rect), 8, 8)

        arc_rect = QRectF(rect.left() + 8, rect.top() + 26, rect.width() - 16, rect.height() * 1.42)
        span_degrees = 210
        start_degrees = 165

        painter.setPen(QPen(QColor(60, 75, 88), 12, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(arc_rect, start_degrees * 16, -span_degrees * 16)

        ratio = self._ratio()
        if self.value is not None:
            gradient = QLinearGradient(rect.topLeft(), rect.topRight())
            gradient.setColorAt(0.0, QColor("#27c08a"))
            gradient.setColorAt(0.55, QColor("#2aa9c0"))
            gradient.setColorAt(1.0, QColor("#ef5b5b"))
            painter.setPen(QPen(QBrush(gradient), 12, Qt.SolidLine, Qt.RoundCap))
            painter.drawArc(arc_rect, start_degrees * 16, int(-span_degrees * ratio * 16))

        painter.setPen(QColor("#a9b7c4"))
        font = QFont(FONT_FAMILY, 9)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignTop | Qt.AlignHCenter, self.title)

        value_text = "--" if self.value is None else f"{self.value:.1f}"
        font = QFont(FONT_FAMILY, 24)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor("#eef7fb"))
        painter.drawText(rect.adjusted(0, 44, 0, 0), Qt.AlignHCenter | Qt.AlignTop, value_text)

        font = QFont(FONT_FAMILY, 10)
        painter.setFont(font)
        painter.setPen(QColor("#8da1b2"))
        painter.drawText(rect.adjusted(0, 82, 0, 0), Qt.AlignHCenter | Qt.AlignTop, self.unit)

        painter.setPen(QColor("#c9d6e2"))
        painter.drawText(rect.adjusted(0, 112, 0, 0), Qt.AlignHCenter | Qt.AlignTop, self.caption)

    def _ratio(self) -> float:
        if self.value is None or self.maximum <= self.minimum:
            return 0.0
        return clamp((self.value - self.minimum) / (self.maximum - self.minimum), 0.0, 1.0)


class MetricBar(QWidget):
    def __init__(
        self,
        title: str,
        unit: str = "",
        minimum: float = 0.0,
        maximum: float = 1.0,
        invert_color: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.title = title
        self.unit = unit
        self.minimum = minimum
        self.maximum = maximum
        self.invert_color = invert_color
        self.value: Optional[float] = None
        self.display_text = "--"
        self.detail_text = ""
        self.setMinimumHeight(58)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_metric(
        self,
        value: Optional[float],
        display_text: str | None = None,
        detail_text: str = "",
    ) -> None:
        self.value = value
        if display_text is not None:
            self.display_text = display_text
        elif value is None:
            self.display_text = "--"
        else:
            self.display_text = f"{value:.2f} {self.unit}".strip()
        self.detail_text = detail_text
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(240, 58)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        bounds = self.rect().adjusted(8, 5, -8, -5)
        painter.setPen(QPen(QColor("#2c3845"), 1))
        painter.setBrush(QColor("#141b22"))
        painter.drawRoundedRect(QRectF(self.rect().adjusted(2, 2, -2, -2)), 8, 8)

        painter.setPen(QColor("#a9b7c4"))
        title_font = QFont(FONT_FAMILY, 9)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.drawText(bounds.left(), bounds.top() + 13, self.title)

        value_font = QFont(FONT_FAMILY, 11)
        value_font.setBold(True)
        painter.setFont(value_font)
        painter.setPen(QColor("#eef7fb"))
        painter.drawText(bounds, Qt.AlignTop | Qt.AlignRight, self.display_text)

        track = QRectF(bounds.left(), bounds.top() + 25, bounds.width(), 11)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(49, 64, 78))
        painter.drawRoundedRect(track, 5, 5)

        ratio = self._ratio()
        if self.value is not None and ratio > 0:
            fill = QRectF(track.left(), track.top(), max(8.0, track.width() * ratio), track.height())
            painter.setBrush(level_color(ratio, self.invert_color))
            painter.drawRoundedRect(fill, 5, 5)

        if self.detail_text:
            painter.setPen(QColor("#8da1b2"))
            detail_font = QFont(FONT_FAMILY, 8)
            painter.setFont(detail_font)
            painter.drawText(bounds.left(), bounds.bottom() - 1, self.detail_text)

    def _ratio(self) -> float:
        if self.value is None or self.maximum <= self.minimum:
            return 0.0
        return clamp((self.value - self.minimum) / (self.maximum - self.minimum), 0.0, 1.0)


class StatusBadge(QWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title_label = QLabel(title)
        self.value_label = QLabel("--")
        self.title_label.setObjectName("BadgeTitle")
        self.value_label.setObjectName("BadgeValue")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        self.setMinimumHeight(60)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.set_status("--", "#64748b")

    def set_status(self, text: str, color: str) -> None:
        self.value_label.setText(text or "--")
        self.setStyleSheet(
            f"""
            StatusBadge {{
                background-color: rgba(255, 255, 255, 0.035);
                border: 1px solid {color};
                border-radius: 6px;
            }}
            QLabel#BadgeTitle {{
                color: #8da1b2;
                font-size: 10px;
                font-weight: bold;
            }}
            QLabel#BadgeValue {{
                color: #eef7fb;
                font-size: 16px;
                font-weight: bold;
            }}
            """
        )


def status_color(text: str, ok_words: tuple[str, ...], warn_words: tuple[str, ...]) -> str:
    lowered = text.lower()
    if any(word.lower() in lowered for word in ok_words):
        return "#27c08a"
    if any(word.lower() in lowered for word in warn_words):
        return "#f6b94d"
    return "#2aa9c0"
