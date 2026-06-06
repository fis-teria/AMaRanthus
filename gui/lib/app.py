import argparse
import sys
from pathlib import Path

from PyQt5.QtCore import QLocale, Qt
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtWebEngineWidgets import QWebEngineSettings

from .main_window import MainWindow, build_data_sources
from .theme import apply_app_theme
from .ui_config import load_ui_render_config


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Robot UI Sample")
    parser.add_argument(
        "--data-source",
        choices=["demo", "ros2"],
        default="demo",
        help="UIに流し込むデータソースを選択します。",
    )
    parser.add_argument("--ui-config", default=None)
    parser.add_argument(
        "--theme",
        choices=["dark", "light"],
        default="dark",
        help="GUIの配色テーマを選択します。",
    )
    parser.add_argument("--ros-camera-image-topic", default="/sensing/camera/camera0/image_rect_color")
    parser.add_argument("--ros-camera-overlay-topic", default="/shadow/e2e/overlay_image")
    parser.add_argument(
        "--ros-camera-compressed-overlay-topic",
        default="/shadow/e2e/overlay_image/compressed",
    )
    parser.add_argument("--ros-camera-overlay-timeout-sec", type=float, default=1.0)
    parser.add_argument(
        "--no-ros-camera-raw-overlay-fallback",
        dest="ros_camera_raw_overlay_fallback",
        action="store_false",
        default=True,
        help="Compressed overlay imageだけを購読し、raw overlay image fallbackを無効化します。",
    )
    parser.add_argument(
        "--no-ros-camera-raw-fallback",
        dest="ros_camera_raw_fallback",
        action="store_false",
        default=True,
        help="Overlay imageだけを購読し、raw camera image fallbackを無効化します。",
    )
    parser.add_argument("--ros-camera-display-max-edge-px", type=int, default=1280)
    parser.add_argument("--ros-camera-info-topic", default="/sensing/camera/camera0/camera_info")
    parser.add_argument("--ros-pointcloud-topic", default="/cloud_registered")
    parser.add_argument("--ros-pointcloud-odom-topic", default="/Odometry")
    parser.add_argument(
        "--no-ros-pointcloud-stabilize-with-odom",
        dest="ros_pointcloud_stabilize_with_odom",
        action="store_false",
        default=True,
        help="PointCloud2をodometry poseで現在車両基準へ戻す処理を無効化します。",
    )
    parser.add_argument("--ros-pointcloud-max-points", type=int, default=2500)
    parser.add_argument("--ros-pointcloud-min-update-interval-sec", type=float, default=0.2)
    parser.add_argument("--ros-pointcloud-max-range-m", type=float, default=80.0)
    parser.add_argument("--ros-pointcloud-z-min-m", type=float, default=-3.0)
    parser.add_argument("--ros-pointcloud-z-max-m", type=float, default=3.0)
    parser.add_argument("--ros-route-pointcloud-topic", default="/shadow/route/pointcloud")
    parser.add_argument("--ros-route-pointcloud-max-points", type=int, default=1500)
    parser.add_argument("--ros-route-path-topic", default="/shadow/route/gui_path")
    parser.add_argument("--ros-route-target-topic", default="/shadow/route/target_point")
    parser.add_argument("--ros-route-target-path-topic", default="/shadow/route/target_path")
    parser.add_argument("--ros-e2e-path-topic", default="/shadow/e2e/path")
    parser.add_argument("--ros-e2e-raw-lead-path-topic", default="/shadow/e2e/path_raw_lead")
    parser.add_argument("--ros-e2e-status-topic", default="/shadow/e2e/status")
    parser.add_argument("--ros-e2e-model-input-image-topic", default="/shadow/e2e/model_input_image")
    parser.add_argument("--ros-e2e-pointcloud-topic", default="/cloud_registered_body")
    parser.add_argument("--ros-scan-topic", default="/scan")
    parser.add_argument("--ros-lane-topic", default="/scan")
    parser.add_argument("--ros-objects-topic", default="/detected_objects")
    parser.add_argument("--ros-speed-topic", default="/vehicle/speed_kmh")
    parser.add_argument("--ros-mode-topic", default="/vehicle/mode")
    parser.add_argument("--ros-gps-topic", default="/vehicle/gps_status")
    parser.add_argument("--ros-phone-fix-topic", default="/phone/gps/fix")
    parser.add_argument("--ros-phone-goal-topic", default="/phone/route/goal")
    parser.add_argument("--ros-phone-status-topic", default="/phone/location/status")
    parser.add_argument("--ros-shadow-ego-speed-topic", default="/shadow/ego/speed")
    parser.add_argument("--ros-shadow-ego-yaw-rate-topic", default="/shadow/ego/yaw_rate")
    parser.add_argument("--ros-shadow-ego-curvature-topic", default="/shadow/ego/curvature")
    parser.add_argument(
        "--ros-shadow-virtual-steering-topic",
        default="/shadow/virtual/steering_proxy",
    )
    parser.add_argument("--ros-shadow-virtual-curvature-topic", default="/shadow/virtual/curvature")
    parser.add_argument("--ros-shadow-virtual-warning-topic", default="/shadow/virtual/warning_score")
    parser.add_argument(
        "--ros-shadow-driver-steering-topic",
        default="/shadow/metrics/driver_steering_proxy",
    )
    parser.add_argument(
        "--ros-shadow-steering-delta-topic",
        default="/shadow/metrics/steering_delta",
    )
    parser.add_argument(
        "--ros-shadow-curvature-delta-topic",
        default="/shadow/metrics/curvature_delta",
    )
    parser.add_argument(
        "--ros-shadow-intervention-score-topic",
        default="/shadow/metrics/intervention_score",
    )
    parser.add_argument("--ros-shadow-summary-topic", default="/shadow/metrics/summary")
    parser.add_argument("--tts-backend-url", default="http://127.0.0.1:8766")
    parser.add_argument(
        "--disable-route-voice-guidance",
        action="store_true",
        help="OSRM/phone route guidance textのIrodori音声案内を無効化します。",
    )
    parser.add_argument("--route-voice-preannounce-distance-m", type=float, default=300.0)
    parser.add_argument("--route-voice-early-preannounce-distance-m", type=float, default=1000.0)
    parser.add_argument("--gpu-monitor-interval-sec", type=float, default=1.0)
    parser.add_argument("--disable-gpu-monitor", action="store_true")
    parser.add_argument(
        "--rosbag-record-dir",
        default=None,
        help="GUIの録画ボタンで保存するrosbagディレクトリ。",
    )
    parser.add_argument(
        "--rosbag-record-topic",
        action="append",
        default=[],
        help="GUIの録画ボタンで追加保存するROS2 topic。複数指定できます。",
    )
    parser.add_argument(
        "--rosbag-record-preset",
        default="E2E input",
        help="GUIの録画ボタンで最初に選択する録画プリセット。",
    )
    return parser.parse_args(argv)


def _default_rosbag_record_dir() -> str:
    helianthus_dir = Path(__file__).resolve().parents[3]
    return str(helianthus_dir / "Data" / "gui_rosbags")


def _rosbag_record_topics(args: argparse.Namespace) -> list[str]:
    return _unique_topics(
        [
            args.ros_pointcloud_topic,
            args.ros_e2e_pointcloud_topic,
            args.ros_pointcloud_odom_topic,
            args.ros_route_pointcloud_topic,
            args.ros_route_path_topic,
            args.ros_route_target_topic,
            args.ros_route_target_path_topic,
            args.ros_e2e_path_topic,
            args.ros_e2e_raw_lead_path_topic,
            args.ros_e2e_status_topic,
            args.ros_e2e_model_input_image_topic,
            args.ros_camera_image_topic,
            args.ros_camera_overlay_topic,
            args.ros_camera_compressed_overlay_topic,
            args.ros_camera_info_topic,
            args.ros_phone_fix_topic,
            args.ros_phone_goal_topic,
            args.ros_phone_status_topic,
            args.ros_gps_topic,
            "/tf",
            "/tf_static",
            *args.rosbag_record_topic,
        ]
    )


def _rosbag_record_presets(args: argparse.Namespace) -> dict[str, list[str]]:
    extra_topics = list(args.rosbag_record_topic)
    e2e_input_topics = _unique_topics(
        [
            args.ros_pointcloud_topic,
            args.ros_e2e_pointcloud_topic,
            args.ros_pointcloud_odom_topic,
            args.ros_camera_image_topic,
            args.ros_camera_info_topic,
            args.ros_e2e_model_input_image_topic,
            args.ros_e2e_path_topic,
            args.ros_e2e_raw_lead_path_topic,
            args.ros_e2e_status_topic,
            args.ros_phone_fix_topic,
            args.ros_phone_goal_topic,
            args.ros_phone_status_topic,
            args.ros_route_path_topic,
            args.ros_route_target_topic,
            args.ros_route_target_path_topic,
            args.ros_gps_topic,
            "/tf",
            "/tf_static",
            *extra_topics,
        ]
    )
    gui_replay_topics = _unique_topics(
        [
            *e2e_input_topics,
            args.ros_camera_overlay_topic,
            args.ros_camera_compressed_overlay_topic,
            args.ros_shadow_ego_speed_topic,
            args.ros_shadow_ego_yaw_rate_topic,
            args.ros_shadow_ego_curvature_topic,
            args.ros_shadow_virtual_steering_topic,
            args.ros_shadow_virtual_curvature_topic,
            args.ros_shadow_virtual_warning_topic,
            args.ros_shadow_driver_steering_topic,
            args.ros_shadow_steering_delta_topic,
            args.ros_shadow_curvature_delta_topic,
            args.ros_shadow_intervention_score_topic,
            args.ros_shadow_summary_topic,
            args.ros_e2e_path_topic,
            args.ros_e2e_raw_lead_path_topic,
            args.ros_e2e_status_topic,
            "/shadow/e2e/steering_proxy",
            "/shadow/e2e/curvature",
            "/shadow/e2e/speed_target",
            "/shadow/e2e/confidence",
            args.ros_route_path_topic,
            args.ros_route_pointcloud_topic,
            args.ros_route_target_topic,
            args.ros_route_target_path_topic,
            "/shadow/route/command",
            "/shadow/fused/odometry",
            "/shadow/fused/path",
            "/shadow/fused/status",
            "/yolo/detections",
        ]
    )
    return {
        "E2E input": e2e_input_topics,
        "GUI replay": gui_replay_topics,
    }


def _unique_topics(topics: list[str]) -> list[str]:
    unique_topics = []
    seen = set()
    for topic in topics:
        topic = str(topic).strip()
        if not topic or topic in seen:
            continue
        unique_topics.append(topic)
        seen.add(topic)
    return unique_topics


def main() -> None:
    args = parse_args(sys.argv[1:])

    QLocale.setDefault(QLocale(QLocale.Japanese, QLocale.Japan))

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_DontCreateNativeWidgetSiblings, True)
    active_theme = apply_app_theme(args.theme)

    settings = QWebEngineSettings.globalSettings()
    settings.setAttribute(QWebEngineSettings.PluginsEnabled, True)
    settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
    settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
    settings.setAttribute(QWebEngineSettings.AllowWindowActivationFromJavaScript, True)
    settings.setAttribute(QWebEngineSettings.JavascriptCanAccessClipboard, True)

    data_sources = build_data_sources(
        ros_camera_image_topic=args.ros_camera_image_topic,
        ros_camera_overlay_topic=args.ros_camera_overlay_topic,
        ros_camera_compressed_overlay_topic=args.ros_camera_compressed_overlay_topic,
        ros_camera_overlay_timeout_sec=args.ros_camera_overlay_timeout_sec,
        ros_camera_raw_overlay_fallback=args.ros_camera_raw_overlay_fallback,
        ros_camera_raw_fallback=args.ros_camera_raw_fallback,
        ros_camera_display_max_edge_px=args.ros_camera_display_max_edge_px,
        ros_camera_info_topic=args.ros_camera_info_topic,
        ros_pointcloud_topic=args.ros_pointcloud_topic,
        ros_pointcloud_odom_topic=args.ros_pointcloud_odom_topic,
        ros_pointcloud_stabilize_with_odom=args.ros_pointcloud_stabilize_with_odom,
        ros_pointcloud_max_points=args.ros_pointcloud_max_points,
        ros_pointcloud_min_update_interval_sec=args.ros_pointcloud_min_update_interval_sec,
        ros_pointcloud_max_range_m=args.ros_pointcloud_max_range_m,
        ros_pointcloud_z_min_m=args.ros_pointcloud_z_min_m,
        ros_pointcloud_z_max_m=args.ros_pointcloud_z_max_m,
        ros_route_pointcloud_topic=args.ros_route_pointcloud_topic,
        ros_route_pointcloud_max_points=args.ros_route_pointcloud_max_points,
        ros_route_path_topic=args.ros_route_path_topic,
        ros_e2e_path_topic=args.ros_e2e_path_topic,
        ros_scan_topic=args.ros_scan_topic,
        ros_lane_topic=args.ros_lane_topic,
        ros_objects_topic=args.ros_objects_topic,
        ros_speed_topic=args.ros_speed_topic,
        ros_mode_topic=args.ros_mode_topic,
        ros_gps_topic=args.ros_gps_topic,
        ros_phone_fix_topic=args.ros_phone_fix_topic,
        ros_phone_goal_topic=args.ros_phone_goal_topic,
        ros_phone_status_topic=args.ros_phone_status_topic,
        ros_shadow_ego_speed_topic=args.ros_shadow_ego_speed_topic,
        ros_shadow_ego_yaw_rate_topic=args.ros_shadow_ego_yaw_rate_topic,
        ros_shadow_ego_curvature_topic=args.ros_shadow_ego_curvature_topic,
        ros_shadow_virtual_steering_topic=args.ros_shadow_virtual_steering_topic,
        ros_shadow_virtual_curvature_topic=args.ros_shadow_virtual_curvature_topic,
        ros_shadow_virtual_warning_topic=args.ros_shadow_virtual_warning_topic,
        ros_shadow_driver_steering_topic=args.ros_shadow_driver_steering_topic,
        ros_shadow_steering_delta_topic=args.ros_shadow_steering_delta_topic,
        ros_shadow_curvature_delta_topic=args.ros_shadow_curvature_delta_topic,
        ros_shadow_intervention_score_topic=args.ros_shadow_intervention_score_topic,
        ros_shadow_summary_topic=args.ros_shadow_summary_topic,
    )
    render_config = load_ui_render_config(args.ui_config)
    try:
        window = MainWindow(
            data_sources,
            render_config,
            initial_data_source=args.data_source,
            initial_theme=active_theme,
            pointcloud_view_range_m=args.ros_pointcloud_max_range_m,
            pointcloud_view_z_min_m=args.ros_pointcloud_z_min_m,
            pointcloud_view_z_max_m=args.ros_pointcloud_z_max_m,
            route_voice_guidance_enabled=not args.disable_route_voice_guidance,
            tts_backend_url=args.tts_backend_url,
            route_voice_preannounce_distance_m=args.route_voice_preannounce_distance_m,
            route_voice_early_preannounce_distance_m=args.route_voice_early_preannounce_distance_m,
            gpu_monitor_interval_sec=args.gpu_monitor_interval_sec,
            gpu_monitor_enabled=not args.disable_gpu_monitor,
            rosbag_record_dir=args.rosbag_record_dir or _default_rosbag_record_dir(),
            rosbag_record_topics=_rosbag_record_topics(args),
            rosbag_record_presets=_rosbag_record_presets(args),
            rosbag_default_record_preset=args.rosbag_record_preset,
        )
    except RuntimeError as exc:
        QMessageBox.critical(None, "起動エラー", str(exc))
        sys.exit(1)
    window.show()
    window.raise_()
    window.activateWindow()
    sys.exit(app.exec_())
