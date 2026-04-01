import argparse
import sys

from PyQt5.QtCore import QLocale, Qt
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtWebEngineWidgets import QWebEngineSettings

from .main_window import MainWindow, build_data_source
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
    parser.add_argument("--ros-scan-topic", default="/scan")
    parser.add_argument("--ros-lane-topic", default="/scan")
    parser.add_argument("--ros-objects-topic", default="/detected_objects")
    parser.add_argument("--ros-speed-topic", default="/vehicle/speed_kmh")
    parser.add_argument("--ros-mode-topic", default="/vehicle/mode")
    parser.add_argument("--ros-gps-topic", default="/vehicle/gps_status")
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args(sys.argv[1:])

    QLocale.setDefault(QLocale(QLocale.Japanese, QLocale.Japan))

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_DontCreateNativeWidgetSiblings, True)

    settings = QWebEngineSettings.globalSettings()
    settings.setAttribute(QWebEngineSettings.PluginsEnabled, True)
    settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
    settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
    settings.setAttribute(QWebEngineSettings.AllowWindowActivationFromJavaScript, True)
    settings.setAttribute(QWebEngineSettings.JavascriptCanAccessClipboard, True)

    data_source = build_data_source(
        args.data_source,
        ros_scan_topic=args.ros_scan_topic,
        ros_lane_topic=args.ros_lane_topic,
        ros_objects_topic=args.ros_objects_topic,
        ros_speed_topic=args.ros_speed_topic,
        ros_mode_topic=args.ros_mode_topic,
        ros_gps_topic=args.ros_gps_topic,
    )
    render_config = load_ui_render_config(args.ui_config)
    try:
        window = MainWindow(data_source, render_config)
    except RuntimeError as exc:
        QMessageBox.critical(None, "起動エラー", str(exc))
        sys.exit(1)
    window.show()
    sys.exit(app.exec_())
