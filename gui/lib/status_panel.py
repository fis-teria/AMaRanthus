from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QFrame, QGridLayout, QLabel


class StatusPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)

        layout = QGridLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setHorizontalSpacing(16)
        layout.setVerticalSpacing(10)

        jp_font = QFont()
        jp_font.setFamily("Noto Sans CJK JP, IPAGothic, TakaoGothic, Yu Gothic, MS Gothic, Arial")
        jp_font.setPointSize(10)

        self.labels = {}
        items = [
            ("車速", "-- km/h"),
            ("前方最短距離", "-- m"),
            ("障害物数", "--"),
            ("モード", "--"),
            ("GPS", "--"),
        ]

        for row, (title, value) in enumerate(items):
            title_label = QLabel(title)
            value_label = QLabel(value)
            title_label.setFont(jp_font)
            value_label.setFont(jp_font)
            title_label.setStyleSheet("font-weight: bold;")
            value_label.setStyleSheet("font-size: 18px;")
            layout.addWidget(title_label, row, 0)
            layout.addWidget(value_label, row, 1)
            self.labels[title] = value_label

    def update_status(
        self,
        speed_kmh: float,
        min_distance_m: float,
        obstacle_count: int,
        mode: str,
        gps_status: str,
    ) -> None:
        self.labels["車速"].setText(f"{speed_kmh:.1f} km/h")
        self.labels["前方最短距離"].setText(f"{min_distance_m:.2f} m")
        self.labels["障害物数"].setText(str(obstacle_count))
        self.labels["モード"].setText(mode)
        self.labels["GPS"].setText(gps_status)
