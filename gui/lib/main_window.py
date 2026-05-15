import sys
from datetime import datetime

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .camera_view import CameraView
from .data_sources import DemoDataSource, Ros2DataSource
from .map_widget import MapWidget
from .models import UiState
from .pointcloud_view import PointCloudView
from .sensor_view import SensorView
from .shadow_panel import ShadowMetricsPanel
from .status_panel import StatusPanel
from .ui_config import UiRenderConfig


TOPIC_FIELDS = [
    ("camera", "Camera"),
    ("pointcloud", "Cloud"),
    ("scan", "Scan"),
    ("lane", "Lane"),
    ("objects", "Objects"),
    ("speed", "Speed"),
    ("mode", "Mode"),
    ("gps", "GPS"),
    ("shadow", "Shadow"),
]


class MainWindow(QMainWindow):
    def __init__(
        self,
        data_sources: dict[str, object],
        render_config: UiRenderConfig,
        initial_data_source: str = "demo",
    ):
        super().__init__()
        self._data_sources = data_sources
        self._render_config = render_config
        self._auto_activate_ros2_fields = initial_data_source == "ros2"
        self._active_sources = {field_name: "demo" for field_name, _ in TOPIC_FIELDS}
        self._ros2_available_fields: set[str] = set()
        self._topic_buttons: dict[str, QPushButton] = {}
        self._last_states: dict[str, UiState] = {}
        self.setWindowTitle("Robot UI Sample")
        self.resize(1500, 850)

        splitter = QSplitter(Qt.Horizontal)

        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(6, 6, 6, 6)
        left_layout.setSpacing(6)

        view_switch_bar = QHBoxLayout()
        self.map_view_button = QPushButton("Map")
        self.pointcloud_view_button = QPushButton("PointCloud")
        self.camera_view_button = QPushButton("Camera")
        for button in (self.map_view_button, self.pointcloud_view_button, self.camera_view_button):
            button.setCheckable(True)
            button.setMinimumHeight(32)
        self.camera_view_button.setChecked(True)
        view_switch_bar.addWidget(self.map_view_button)
        view_switch_bar.addWidget(self.pointcloud_view_button)
        view_switch_bar.addWidget(self.camera_view_button)

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
        map_container = QWidget()
        map_layout = QVBoxLayout(map_container)
        map_layout.setContentsMargins(0, 0, 0, 0)
        map_layout.setSpacing(6)
        map_layout.addLayout(route_bar)
        map_layout.addWidget(self.map_widget, 1)

        self.pointcloud_view = PointCloudView()
        self.camera_view = CameraView()
        self.left_stack = QStackedWidget()
        self.left_stack.addWidget(map_container)
        self.left_stack.addWidget(self.pointcloud_view)
        self.left_stack.addWidget(self.camera_view)
        self._left_view_indexes = {"map": 0, "pointcloud": 1, "camera": 2}
        self.left_stack.setCurrentIndex(self._left_view_indexes["camera"])

        left_layout.addLayout(view_switch_bar)
        left_layout.addWidget(self.left_stack, 1)

        self.search_button.clicked.connect(self.on_search_route)
        self.start_input.returnPressed.connect(self.on_search_route)
        self.end_input.returnPressed.connect(self.on_search_route)
        self.map_view_button.clicked.connect(lambda: self.switch_left_view("map"))
        self.pointcloud_view_button.clicked.connect(lambda: self.switch_left_view("pointcloud"))
        self.camera_view_button.clicked.connect(lambda: self.switch_left_view("camera"))

        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(6, 6, 6, 6)
        right_layout.setSpacing(6)

        source_grid = QGridLayout()
        source_grid.setHorizontalSpacing(6)
        source_grid.setVerticalSpacing(6)
        for index, (field_name, _) in enumerate(TOPIC_FIELDS):
            button = QPushButton()
            button.setCheckable(True)
            button.setEnabled(False)
            button.setMinimumWidth(92)
            button.setToolTip("ROS2 topic waiting")
            button.clicked.connect(
                lambda checked, name=field_name: self.switch_topic_source(name, checked)
            )
            source_grid.addWidget(button, index // 4, index % 4)
            self._topic_buttons[field_name] = button
            self._update_topic_button(field_name)

        self.status_panel = StatusPanel()
        self.shadow_panel = ShadowMetricsPanel()
        self.sensor_view = SensorView(render_config=self._render_config)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(500)
        self.log_view.setMinimumHeight(120)
        self.log_view.setMaximumHeight(180)
        self.log_view.setPlaceholderText("GUI logs")

        right_layout.addLayout(source_grid)
        right_layout.addWidget(self.status_panel, 0)
        right_layout.addWidget(self.shadow_panel, 0)
        right_layout.addWidget(self.sensor_view, 1)
        right_layout.addWidget(self.log_view, 0)

        splitter.addWidget(left_container)
        splitter.addWidget(right_container)
        splitter.setSizes([850, 650])
        self.setCentralWidget(splitter)

        self.log_message("INFO", f"GUI started with initial source: {initial_data_source}")
        self._start_data_sources()

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
        self.shadow_panel.update_metrics(state.shadow)

        self.sensor_view.set_data(
            scan_xy_m=state.scan_points,
            lane_xy_m=state.lane_points,
            objects=state.objects,
            speed_kmh=state.speed_kmh,
            min_distance_m=state.min_distance_m,
        )
        self.pointcloud_view.set_points(state.pointcloud_points)
        self.camera_view.set_frame(state.camera_frame)

    def switch_left_view(self, view_name: str) -> None:
        self.left_stack.setCurrentIndex(self._left_view_indexes.get(view_name, 0))

        self.map_view_button.blockSignals(True)
        self.pointcloud_view_button.blockSignals(True)
        self.camera_view_button.blockSignals(True)
        self.map_view_button.setChecked(view_name == "map")
        self.pointcloud_view_button.setChecked(view_name == "pointcloud")
        self.camera_view_button.setChecked(view_name == "camera")
        self.map_view_button.blockSignals(False)
        self.pointcloud_view_button.blockSignals(False)
        self.camera_view_button.blockSignals(False)

    def switch_topic_source(self, field_name: str, use_ros2: bool) -> None:
        if use_ros2 and field_name not in self._ros2_available_fields:
            self._active_sources[field_name] = "demo"
            self._update_topic_button(field_name)
            return

        self._active_sources[field_name] = "ros2" if use_ros2 else "demo"
        self._update_topic_button(field_name)
        self._apply_composed_state()

    def _start_data_sources(self) -> None:
        demo_source = self._data_sources["demo"]
        demo_source.start(lambda state: self._on_data_source_state("demo", state))
        self.log_message("INFO", "Demo data source started.")

        ros2_source = self._data_sources.get("ros2")
        if ros2_source is None:
            self.log_message("WARN", "ROS2 data source is not configured.")
            return

        ros2_source.set_live_callback(self._on_ros2_field_live)
        ros2_source.set_log_callback(self.log_message)
        try:
            ros2_source.start(lambda state: self._on_data_source_state("ros2", state))
        except RuntimeError as exc:
            print(f"[WARN] ROS2 data source disabled: {exc}", file=sys.stderr)
            self.log_message("WARN", f"ROS2 data source disabled: {exc}")
            for button in self._topic_buttons.values():
                button.setToolTip(str(exc))

    def _on_data_source_state(self, source_name: str, state: UiState) -> None:
        self._last_states[source_name] = state
        if source_name == "demo" or source_name in self._active_sources.values():
            self._apply_composed_state()

    def _on_ros2_field_live(self, field_name: str) -> None:
        if field_name not in self._active_sources:
            return

        was_available = field_name in self._ros2_available_fields
        self._ros2_available_fields.add(field_name)
        if self._auto_activate_ros2_fields:
            self._active_sources[field_name] = "ros2"

        self._update_topic_button(field_name)
        self._apply_composed_state()
        if not was_available:
            self.log_message("INFO", f"ROS2 field enabled: {self._topic_label(field_name)}")

    def _apply_composed_state(self) -> None:
        demo_state = self._last_states.get("demo")
        if demo_state is None:
            return

        ros2_state = self._last_states.get("ros2")
        self.apply_ui_state(self._compose_state(demo_state, ros2_state))

    def _compose_state(self, demo_state: UiState, ros2_state: UiState | None) -> UiState:
        def field_source(field_name: str) -> UiState:
            if (
                self._active_sources.get(field_name) == "ros2"
                and field_name in self._ros2_available_fields
                and ros2_state is not None
            ):
                return ros2_state
            return demo_state

        scan_state = field_source("scan")
        objects_state = field_source("objects")

        return UiState(
            scan_points=scan_state.scan_points,
            lane_points=field_source("lane").lane_points,
            pointcloud_points=field_source("pointcloud").pointcloud_points,
            objects=objects_state.objects,
            speed_kmh=field_source("speed").speed_kmh,
            min_distance_m=scan_state.min_distance_m,
            obstacle_count=objects_state.obstacle_count,
            mode=field_source("mode").mode,
            gps_status=field_source("gps").gps_status,
            shadow=field_source("shadow").shadow,
            camera_frame=field_source("camera").camera_frame,
        )

    def _update_topic_button(self, field_name: str) -> None:
        button = self._topic_buttons[field_name]
        source_name = self._active_sources.get(field_name, "demo")
        ros2_available = field_name in self._ros2_available_fields

        button.blockSignals(True)
        button.setChecked(source_name == "ros2" and ros2_available)
        button.setEnabled(ros2_available)
        source_label = "ROS2" if button.isChecked() else "Demo"
        button.setText(f"{self._topic_label(field_name)}: {source_label}")
        button.setToolTip("ROS2 topic active" if ros2_available else "ROS2 topic waiting")
        button.blockSignals(False)

    def _topic_label(self, field_name: str) -> str:
        return dict(TOPIC_FIELDS)[field_name]

    def log_message(self, level: str, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"{timestamp} [{level}] {message}"
        print(line)
        self.log_view.appendPlainText(line)
        scrollbar = self.log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def closeEvent(self, event):
        for data_source in self._data_sources.values():
            data_source.stop()
        super().closeEvent(event)


def build_data_sources(
    *,
    ros_camera_image_topic: str,
    ros_camera_info_topic: str,
    ros_pointcloud_topic: str,
    ros_scan_topic: str,
    ros_lane_topic: str,
    ros_objects_topic: str,
    ros_speed_topic: str,
    ros_mode_topic: str,
    ros_gps_topic: str,
    ros_shadow_ego_speed_topic: str,
    ros_shadow_ego_yaw_rate_topic: str,
    ros_shadow_ego_curvature_topic: str,
    ros_shadow_virtual_steering_topic: str,
    ros_shadow_virtual_curvature_topic: str,
    ros_shadow_virtual_warning_topic: str,
    ros_shadow_driver_steering_topic: str,
    ros_shadow_steering_delta_topic: str,
    ros_shadow_curvature_delta_topic: str,
    ros_shadow_intervention_score_topic: str,
    ros_shadow_summary_topic: str,
):
    return {
        "demo": DemoDataSource(),
        "ros2": Ros2DataSource(
            camera_image_topic=ros_camera_image_topic,
            camera_info_topic=ros_camera_info_topic,
            pointcloud_topic=ros_pointcloud_topic,
            scan_topic=ros_scan_topic,
            lane_topic=ros_lane_topic,
            objects_topic=ros_objects_topic,
            speed_topic=ros_speed_topic,
            mode_topic=ros_mode_topic,
            gps_topic=ros_gps_topic,
            shadow_ego_speed_topic=ros_shadow_ego_speed_topic,
            shadow_ego_yaw_rate_topic=ros_shadow_ego_yaw_rate_topic,
            shadow_ego_curvature_topic=ros_shadow_ego_curvature_topic,
            shadow_virtual_steering_topic=ros_shadow_virtual_steering_topic,
            shadow_virtual_curvature_topic=ros_shadow_virtual_curvature_topic,
            shadow_virtual_warning_topic=ros_shadow_virtual_warning_topic,
            shadow_driver_steering_topic=ros_shadow_driver_steering_topic,
            shadow_steering_delta_topic=ros_shadow_steering_delta_topic,
            shadow_curvature_delta_topic=ros_shadow_curvature_delta_topic,
            shadow_intervention_score_topic=ros_shadow_intervention_score_topic,
            shadow_summary_topic=ros_shadow_summary_topic,
        ),
    }
