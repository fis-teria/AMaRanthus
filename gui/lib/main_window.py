import sys
from datetime import datetime

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
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
from .system_monitor import GpuMonitor, GpuStatus
from .theme import apply_app_theme, normalize_theme
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

LEFT_INITIAL_WIDTH = 850
RIGHT_TELEMETRY_WIDTH = 650
TOP_BAR_BUTTON_HEIGHT = 32
TOP_BAR_MARGIN_Y = 2


class MainWindow(QMainWindow):
    def __init__(
        self,
        data_sources: dict[str, object],
        render_config: UiRenderConfig,
        initial_data_source: str = "demo",
        initial_theme: str = "dark",
        pointcloud_view_range_m: float = 80.0,
        pointcloud_view_z_min_m: float = -3.0,
        pointcloud_view_z_max_m: float = 3.0,
        gpu_monitor_interval_sec: float = 1.0,
        gpu_monitor_enabled: bool = True,
    ):
        super().__init__()
        self._data_sources = data_sources
        self._render_config = render_config
        self._gpu_monitor = GpuMonitor(
            interval_sec=gpu_monitor_interval_sec,
            enabled=gpu_monitor_enabled,
            parent=self,
        )
        self._auto_activate_ros2_fields = initial_data_source == "ros2"
        self._active_sources = {field_name: "demo" for field_name, _ in TOPIC_FIELDS}
        self._ros2_available_fields: set[str] = set()
        self._topic_buttons: dict[str, QPushButton] = {}
        self._last_states: dict[str, UiState] = {}
        self._current_left_view = "camera"
        self._theme = normalize_theme(initial_theme)
        self._normal_window_geometry = None
        self._normal_window_flags = self.windowFlags()
        self._borderless_full_screen = False
        self.setWindowTitle("Robot UI Sample")
        window_flags = (
            self._normal_window_flags
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowMaximizeButtonHint
            | Qt.WindowCloseButtonHint
        )
        self.setWindowFlags(window_flags)
        self._normal_window_flags = window_flags
        self.resize(1500, 850)

        splitter = QSplitter(Qt.Horizontal)

        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(6, 6, 6, 6)
        left_layout.setSpacing(6)

        view_switch_bar = QHBoxLayout()
        view_switch_bar.setContentsMargins(0, TOP_BAR_MARGIN_Y, 0, TOP_BAR_MARGIN_Y)
        view_switch_bar.setSpacing(6)
        self.map_view_button = QPushButton("Map")
        self.pointcloud_view_button = QPushButton("PointCloud")
        self.camera_view_button = QPushButton("Camera")
        self.full_screen_button = QPushButton("Full")
        self.full_screen_button.setMinimumWidth(72)
        self.full_screen_button.setToolTip("Toggle full screen")
        self.dark_mode_checkbox = QCheckBox("Dark")
        self.dark_mode_checkbox.setMinimumWidth(68)
        self.dark_mode_checkbox.setChecked(self._theme == "dark")
        self.dark_mode_checkbox.setToolTip("Dark theme")
        for button in (
            self.map_view_button,
            self.pointcloud_view_button,
            self.camera_view_button,
            self.full_screen_button,
        ):
            button.setObjectName("TopBarButton")
            button.setCheckable(True)
            button.setFixedHeight(TOP_BAR_BUTTON_HEIGHT)
        self.full_screen_button.setCheckable(False)
        self.dark_mode_checkbox.setObjectName("TopBarCheck")
        self.dark_mode_checkbox.setFixedHeight(TOP_BAR_BUTTON_HEIGHT)
        self.camera_view_button.setChecked(True)
        view_switch_bar.addWidget(self.map_view_button, 0, Qt.AlignVCenter)
        view_switch_bar.addWidget(self.pointcloud_view_button, 0, Qt.AlignVCenter)
        view_switch_bar.addWidget(self.camera_view_button, 0, Qt.AlignVCenter)
        view_switch_bar.addStretch(1)
        view_switch_bar.addWidget(self.full_screen_button, 0, Qt.AlignVCenter)
        view_switch_bar.addWidget(self.dark_mode_checkbox, 0, Qt.AlignVCenter)

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

        self.pointcloud_view = PointCloudView(
            fixed_range_m=pointcloud_view_range_m,
            fixed_z_min_m=pointcloud_view_z_min_m,
            fixed_z_max_m=pointcloud_view_z_max_m,
        )
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
        self.full_screen_button.clicked.connect(self.toggle_full_screen)
        self.dark_mode_checkbox.stateChanged.connect(self._on_dark_mode_toggled)

        right_container = QWidget()
        right_container.setObjectName("TelemetryPane")
        right_container.setFixedWidth(RIGHT_TELEMETRY_WIDTH)
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
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([LEFT_INITIAL_WIDTH, RIGHT_TELEMETRY_WIDTH])
        self.setCentralWidget(splitter)
        self._apply_theme(self._theme)

        self.log_message("INFO", f"GUI started with initial source: {initial_data_source}")
        self._start_data_sources()
        self._start_gpu_monitor()

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
        self._current_left_view = view_name

        self.map_view_button.blockSignals(True)
        self.pointcloud_view_button.blockSignals(True)
        self.camera_view_button.blockSignals(True)
        self.map_view_button.setChecked(view_name == "map")
        self.pointcloud_view_button.setChecked(view_name == "pointcloud")
        self.camera_view_button.setChecked(view_name == "camera")
        self.map_view_button.blockSignals(False)
        self.pointcloud_view_button.blockSignals(False)
        self.camera_view_button.blockSignals(False)
        self._refresh_pointcloud_parser_state()

    def toggle_full_screen(self) -> None:
        if self._borderless_full_screen or self.isFullScreen():
            self._exit_full_screen()
        else:
            self._enter_full_screen()
        self._update_full_screen_button()

    def _enter_full_screen(self) -> None:
        if not self._borderless_full_screen:
            self._normal_window_geometry = self.geometry()
            self._normal_window_flags = self.windowFlags()

        self._borderless_full_screen = True
        self.setWindowFlags(self._normal_window_flags | Qt.FramelessWindowHint)
        display_geometry = self._current_available_geometry()
        if display_geometry is not None:
            self.setGeometry(display_geometry)
        self.show()
        if display_geometry is not None:
            QTimer.singleShot(0, lambda geometry=display_geometry: self.setGeometry(geometry))

    def _exit_full_screen(self) -> None:
        normal_geometry = self._normal_window_geometry
        self._borderless_full_screen = False
        if self.isFullScreen():
            self.showNormal()
        self.setWindowFlags(self._normal_window_flags)
        self.show()
        if normal_geometry is not None:
            QTimer.singleShot(0, lambda geometry=normal_geometry: self.setGeometry(geometry))
        self._normal_window_geometry = None

    def _current_available_geometry(self):
        screen = None
        window = self.windowHandle()
        if window is not None:
            screen = window.screen()
        if screen is None:
            screen = QApplication.screenAt(self.frameGeometry().center())
        if screen is None:
            screen = QApplication.primaryScreen()
        if screen is None:
            return None
        return screen.availableGeometry()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and (self._borderless_full_screen or self.isFullScreen()):
            self._exit_full_screen()
            self._update_full_screen_button()
            event.accept()
            return
        if event.key() == Qt.Key_F11:
            self.toggle_full_screen()
            event.accept()
            return
        super().keyPressEvent(event)

    def changeEvent(self, event):
        super().changeEvent(event)
        self._update_full_screen_button()

    def _update_full_screen_button(self) -> None:
        if not hasattr(self, "full_screen_button"):
            return
        if self._borderless_full_screen or self.isFullScreen():
            self.full_screen_button.setText("Exit")
            self.full_screen_button.setMinimumWidth(72)
            self.full_screen_button.setToolTip("Exit borderless window")
        else:
            self.full_screen_button.setText("Full")
            self.full_screen_button.setMinimumWidth(72)
            self.full_screen_button.setToolTip("Enter borderless window")

    def switch_topic_source(self, field_name: str, use_ros2: bool) -> None:
        if use_ros2 and field_name not in self._ros2_available_fields:
            self._active_sources[field_name] = "demo"
            self._update_topic_button(field_name)
            return

        self._active_sources[field_name] = "ros2" if use_ros2 else "demo"
        self._update_topic_button(field_name)
        self._refresh_pointcloud_parser_state()
        self._apply_composed_state()

    def _on_dark_mode_toggled(self, state: int) -> None:
        self._apply_theme("dark" if state == Qt.Checked else "light")
        self.log_message("INFO", f"Theme switched to: {self._theme}")

    def _apply_theme(self, theme_name: str) -> None:
        self._theme = apply_app_theme(theme_name)
        self.map_widget.set_dark_mode(self._theme == "dark")

        self.dark_mode_checkbox.blockSignals(True)
        self.dark_mode_checkbox.setChecked(self._theme == "dark")
        self.dark_mode_checkbox.blockSignals(False)

    def _start_data_sources(self) -> None:
        if self._auto_activate_ros2_fields:
            self._last_states["demo"] = self._blank_ui_state()
            self.log_message("INFO", "Demo data source kept idle for ROS2-first mode.")
        else:
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
            self._refresh_pointcloud_parser_state()
        except RuntimeError as exc:
            print(f"[WARN] ROS2 data source disabled: {exc}", file=sys.stderr)
            self.log_message("WARN", f"ROS2 data source disabled: {exc}")
            for button in self._topic_buttons.values():
                button.setToolTip(str(exc))

    def _start_gpu_monitor(self) -> None:
        self._gpu_monitor.set_callback(self._on_gpu_status)
        self._gpu_monitor.set_log_callback(self.log_message)
        self._gpu_monitor.start()

    def _on_gpu_status(self, status: GpuStatus) -> None:
        self.status_panel.update_gpu_status(status)

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
        self._refresh_pointcloud_parser_state()
        self._apply_composed_state()
        if not was_available:
            self.log_message("INFO", f"ROS2 field enabled: {self._topic_label(field_name)}")

    def _refresh_pointcloud_parser_state(self) -> None:
        ros2_source = self._data_sources.get("ros2")
        if ros2_source is None or not hasattr(ros2_source, "set_pointcloud_view_enabled"):
            return
        pointcloud_source_is_ros2 = (
            self._active_sources.get("pointcloud") == "ros2"
            and "pointcloud" in self._ros2_available_fields
        )
        ros2_source.set_pointcloud_view_enabled(
            self._current_left_view == "pointcloud" and pointcloud_source_is_ros2
        )

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

    def _blank_ui_state(self) -> UiState:
        return UiState(
            scan_points=[],
            lane_points=[],
            pointcloud_points=[],
            objects=[],
            speed_kmh=0.0,
            min_distance_m=99.0,
            obstacle_count=0,
            mode="--",
            gps_status="--",
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
        self._gpu_monitor.stop()
        for data_source in self._data_sources.values():
            data_source.stop()
        super().closeEvent(event)


def build_data_sources(
    *,
    ros_camera_image_topic: str,
    ros_camera_overlay_topic: str,
    ros_camera_compressed_overlay_topic: str,
    ros_camera_overlay_timeout_sec: float,
    ros_camera_raw_overlay_fallback: bool,
    ros_camera_raw_fallback: bool,
    ros_camera_display_max_edge_px: int,
    ros_camera_info_topic: str,
    ros_pointcloud_topic: str,
    ros_pointcloud_max_points: int,
    ros_pointcloud_min_update_interval_sec: float,
    ros_pointcloud_max_range_m: float,
    ros_pointcloud_z_min_m: float,
    ros_pointcloud_z_max_m: float,
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
            camera_overlay_topic=ros_camera_overlay_topic,
            camera_compressed_overlay_topic=ros_camera_compressed_overlay_topic,
            camera_overlay_timeout_sec=ros_camera_overlay_timeout_sec,
            camera_raw_overlay_fallback=ros_camera_raw_overlay_fallback,
            camera_raw_fallback=ros_camera_raw_fallback,
            camera_display_max_edge_px=ros_camera_display_max_edge_px,
            camera_info_topic=ros_camera_info_topic,
            pointcloud_topic=ros_pointcloud_topic,
            pointcloud_max_points=ros_pointcloud_max_points,
            pointcloud_min_update_interval_sec=ros_pointcloud_min_update_interval_sec,
            pointcloud_max_range_m=ros_pointcloud_max_range_m,
            pointcloud_z_min_m=ros_pointcloud_z_min_m,
            pointcloud_z_max_m=ros_pointcloud_z_max_m,
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
