from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .data_sources import DemoDataSource, Ros2DataSource
from .map_widget import MapWidget
from .models import UiState
from .sensor_view import SensorView
from .status_panel import StatusPanel
from .ui_config import UiRenderConfig


class MainWindow(QMainWindow):
    def __init__(self, data_source, render_config: UiRenderConfig):
        super().__init__()
        self._data_source = data_source
        self._render_config = render_config
        self.setWindowTitle("Robot UI Sample")
        self.resize(1500, 850)

        splitter = QSplitter(Qt.Horizontal)

        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(6, 6, 6, 6)
        left_layout.setSpacing(6)

        route_bar = QHBoxLayout()
        self.start_input = QLineEdit()
        self.end_input = QLineEdit()
        self.search_button = QPushButton("ルート検索")

        self.start_input.setPlaceholderText("出発地を入力（例: 東京駅）")
        self.end_input.setPlaceholderText("目的地を入力（例: 渋谷駅）")
        self.start_input.setClearButtonEnabled(True)
        self.end_input.setClearButtonEnabled(True)

        route_bar.addWidget(self.start_input, 1)
        route_bar.addWidget(self.end_input, 1)
        route_bar.addWidget(self.search_button, 0)

        self.map_widget = MapWidget()
        left_layout.addLayout(route_bar)
        left_layout.addWidget(self.map_widget, 1)

        self.search_button.clicked.connect(self.on_search_route)
        self.start_input.returnPressed.connect(self.on_search_route)
        self.end_input.returnPressed.connect(self.on_search_route)

        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(6, 6, 6, 6)
        right_layout.setSpacing(6)

        self.status_panel = StatusPanel()
        self.sensor_view = SensorView(render_config=self._render_config)

        right_layout.addWidget(self.status_panel, 0)
        right_layout.addWidget(self.sensor_view, 1)

        splitter.addWidget(left_container)
        splitter.addWidget(right_container)
        splitter.setSizes([850, 650])
        self.setCentralWidget(splitter)

        self._data_source.start(self.apply_ui_state)

    def on_search_route(self) -> None:
        start_query = self.start_input.text().strip()
        end_query = self.end_input.text().strip()
        self.map_widget.search_route(start_query, end_query)

    def apply_ui_state(self, state: UiState) -> None:
        self.status_panel.update_status(
            speed_kmh=state.speed_kmh,
            min_distance_m=state.min_distance_m,
            obstacle_count=state.obstacle_count,
            mode=state.mode,
            gps_status=state.gps_status,
        )

        self.sensor_view.set_data(
            scan_xy_m=state.scan_points,
            lane_xy_m=state.lane_points,
            objects=state.objects,
            speed_kmh=state.speed_kmh,
            min_distance_m=state.min_distance_m,
        )

    def closeEvent(self, event):
        self._data_source.stop()
        super().closeEvent(event)


def build_data_source(
    data_source_name: str,
    *,
    ros_scan_topic: str,
    ros_lane_topic: str,
    ros_objects_topic: str,
    ros_speed_topic: str,
    ros_mode_topic: str,
    ros_gps_topic: str,
):
    if data_source_name == "demo":
        return DemoDataSource()

    if data_source_name == "ros2":
        return Ros2DataSource(
            scan_topic=ros_scan_topic,
            lane_topic=ros_lane_topic,
            objects_topic=ros_objects_topic,
            speed_topic=ros_speed_topic,
            mode_topic=ros_mode_topic,
            gps_topic=ros_gps_topic,
        )

    raise ValueError(f"Unsupported data source: {data_source_name}")
