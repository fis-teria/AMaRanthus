import os
import signal
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, Optional

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStyle,
    QVBoxLayout,
    QWidget,
)


LogCallback = Callable[[str, str], None]


class RosbagControlPanel(QWidget):
    def __init__(
        self,
        *,
        output_dir: str | None,
        record_topics: Iterable[str],
        record_presets: Optional[dict[str, Iterable[str]]] = None,
        default_record_preset: str = "",
        log_callback: Optional[LogCallback] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._output_dir = Path(output_dir).expanduser() if output_dir else self._default_output_dir()
        self._record_presets = self._normalize_presets(record_presets, record_topics)
        self._active_preset_name = self._resolve_default_preset(default_record_preset)
        self._log_callback = log_callback
        self._record_process: Optional[subprocess.Popen] = None
        self._play_process: Optional[subprocess.Popen] = None
        self._record_log_file = None
        self._play_log_file = None
        self._last_bag_path: Optional[Path] = self._latest_bag_path()

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(500)
        self._poll_timer.timeout.connect(self._poll_processes)
        self._poll_timer.start()

        self._build_ui()
        self._update_bag_path_display()
        self._update_preset_label()
        self._update_buttons()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        group = QGroupBox("ROS bag")
        group.setObjectName("RosbagPanel")
        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(8, 8, 8, 8)
        group_layout.setSpacing(6)

        self.status_label = QLabel("idle")
        self.status_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        group_layout.addWidget(self.status_label)

        preset_row = QHBoxLayout()
        preset_row.setSpacing(4)
        preset_label = QLabel("Preset")
        self.preset_combo = QComboBox()
        for preset_name in self._record_presets:
            self.preset_combo.addItem(preset_name)
        active_index = self.preset_combo.findText(self._active_preset_name)
        if active_index >= 0:
            self.preset_combo.setCurrentIndex(active_index)
        self.preset_combo.currentTextChanged.connect(self._on_preset_changed)
        preset_row.addWidget(preset_label, 0)
        preset_row.addWidget(self.preset_combo, 1)
        group_layout.addLayout(preset_row)

        path_row = QHBoxLayout()
        path_row.setSpacing(4)
        self.bag_path_edit = QLineEdit()
        self.bag_path_edit.setReadOnly(True)
        self.bag_path_edit.setPlaceholderText(str(self._output_dir))
        self.choose_button = QPushButton("選択")
        self.choose_button.setToolTip("Replay bag directory")
        self.choose_button.clicked.connect(self.choose_bag_directory)
        path_row.addWidget(self.bag_path_edit, 1)
        path_row.addWidget(self.choose_button, 0)
        group_layout.addLayout(path_row)

        button_grid = QGridLayout()
        button_grid.setHorizontalSpacing(4)
        button_grid.setVerticalSpacing(4)
        style = self.style()

        self.record_button = QPushButton("録画")
        self.record_button.setIcon(style.standardIcon(QStyle.SP_DriveHDIcon))
        self.record_button.clicked.connect(self.start_recording)

        self.stop_record_button = QPushButton("録画停止")
        self.stop_record_button.setIcon(style.standardIcon(QStyle.SP_MediaStop))
        self.stop_record_button.clicked.connect(self.stop_recording)

        self.play_button = QPushButton("再生")
        self.play_button.setIcon(style.standardIcon(QStyle.SP_MediaPlay))
        self.play_button.clicked.connect(self.start_replay)

        self.stop_play_button = QPushButton("再生停止")
        self.stop_play_button.setIcon(style.standardIcon(QStyle.SP_MediaStop))
        self.stop_play_button.clicked.connect(self.stop_replay)

        for button in (
            self.record_button,
            self.stop_record_button,
            self.play_button,
            self.stop_play_button,
        ):
            button.setObjectName("TopBarButton")
            button.setMinimumHeight(30)

        button_grid.addWidget(self.record_button, 0, 0)
        button_grid.addWidget(self.stop_record_button, 0, 1)
        button_grid.addWidget(self.play_button, 1, 0)
        button_grid.addWidget(self.stop_play_button, 1, 1)
        group_layout.addLayout(button_grid)

        layout.addWidget(group)

    def start_recording(self) -> None:
        if self._is_running(self._record_process):
            return
        if self._is_running(self._play_process):
            self._log("WARN", "Replay is running; stop replay before recording.")
            return
        record_topics = self._active_record_topics()
        if not record_topics:
            self._log("ERROR", "No rosbag record topics are configured.")
            return

        self._output_dir.mkdir(parents=True, exist_ok=True)
        preset_slug = self._slugify(self._active_preset_name)
        bag_path = self._output_dir / f"gui_{preset_slug}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        log_path = self._output_dir / f"{bag_path.name}.log"
        command = ["ros2", "bag", "record", "-o", str(bag_path), *record_topics]

        try:
            self._record_log_file = open(log_path, "w", encoding="utf-8")
            self._record_process = subprocess.Popen(
                command,
                stdout=self._record_log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        except OSError as exc:
            self._close_record_log()
            self._record_process = None
            self._log("ERROR", f"Failed to start rosbag record: {exc}")
            self._update_buttons()
            return

        self._last_bag_path = bag_path
        self._update_bag_path_display()
        self._log("INFO", f"rosbag recording started: {bag_path}")
        self._log("INFO", f"record preset: {self._active_preset_name}")
        self._log("INFO", "record topics: " + ", ".join(record_topics))
        self._update_buttons()

    def stop_recording(self) -> None:
        if not self._is_running(self._record_process):
            return
        self._request_stop(self._record_process, "rosbag record")
        self._update_buttons()

    def start_replay(self) -> None:
        if self._is_running(self._play_process):
            return
        if self._is_running(self._record_process):
            self._log("WARN", "Recording is running; stop recording before replay.")
            return

        bag_path = self._last_bag_path or self._latest_bag_path()
        if bag_path is None or not self._is_bag_directory(bag_path):
            self._log("WARN", f"No replayable bag directory found under {self._output_dir}.")
            return

        log_path = self._output_dir / f"{bag_path.name}_play.log"
        command = ["ros2", "bag", "play", str(bag_path)]

        try:
            self._play_log_file = open(log_path, "w", encoding="utf-8")
            self._play_process = subprocess.Popen(
                command,
                stdout=self._play_log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        except OSError as exc:
            self._close_play_log()
            self._play_process = None
            self._log("ERROR", f"Failed to start rosbag play: {exc}")
            self._update_buttons()
            return

        self._last_bag_path = bag_path
        self._update_bag_path_display()
        self._log("INFO", f"rosbag replay started: {bag_path}")
        self._update_buttons()

    def stop_replay(self) -> None:
        if not self._is_running(self._play_process):
            return
        self._request_stop(self._play_process, "rosbag play")
        self._update_buttons()

    def choose_bag_directory(self) -> None:
        start_dir = str(self._last_bag_path or self._output_dir)
        selected = QFileDialog.getExistingDirectory(self, "Replay bag directory", start_dir)
        if not selected:
            return
        bag_path = Path(selected).expanduser()
        self._last_bag_path = bag_path
        self._update_bag_path_display()
        if not self._is_bag_directory(bag_path):
            self._log("WARN", f"Selected directory does not contain metadata.yaml: {bag_path}")
        self._update_buttons()

    def _on_preset_changed(self, preset_name: str) -> None:
        if preset_name not in self._record_presets:
            return
        self._active_preset_name = preset_name
        self._update_preset_label()
        self._log(
            "INFO",
            f"rosbag record preset selected: {preset_name} ({len(self._active_record_topics())} topics)",
        )

    def stop_all(self) -> None:
        if self._is_running(self._record_process):
            self._request_stop(self._record_process, "rosbag record")
            self._wait_for_process(self._record_process, "rosbag record")
        if self._is_running(self._play_process):
            self._request_stop(self._play_process, "rosbag play")
            self._wait_for_process(self._play_process, "rosbag play")
        self._poll_processes()

    def _poll_processes(self) -> None:
        record_returncode = self._poll_process(self._record_process)
        if record_returncode is not None:
            self._record_process = None
            self._close_record_log()
            if record_returncode == 0:
                self._log("INFO", "rosbag recording stopped.")
            else:
                self._log("WARN", f"rosbag record exited with code {record_returncode}.")

        play_returncode = self._poll_process(self._play_process)
        if play_returncode is not None:
            self._play_process = None
            self._close_play_log()
            if play_returncode == 0:
                self._log("INFO", "rosbag replay finished.")
            else:
                self._log("WARN", f"rosbag play exited with code {play_returncode}.")

        self._update_buttons()

    def _poll_process(self, process: Optional[subprocess.Popen]) -> Optional[int]:
        if process is None:
            return None
        return process.poll()

    def _request_stop(self, process: subprocess.Popen, label: str) -> None:
        try:
            os.killpg(process.pid, signal.SIGINT)
            self._log("INFO", f"Stopping {label}...")
        except ProcessLookupError:
            return
        except OSError as exc:
            self._log("WARN", f"Failed to stop {label}: {exc}")
            return
        QTimer.singleShot(5000, lambda proc=process, name=label: self._kill_if_running(proc, name))

    def _kill_if_running(self, process: subprocess.Popen, label: str) -> None:
        if not self._is_running(process):
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
            self._log("WARN", f"{label} did not exit after SIGINT; sent SIGTERM.")
        except ProcessLookupError:
            return
        except OSError as exc:
            self._log("WARN", f"Failed to terminate {label}: {exc}")

    def _wait_for_process(self, process: subprocess.Popen, label: str) -> None:
        try:
            process.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            self._kill_if_running(process, label)
            try:
                process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                self._log("WARN", f"{label} is still running after termination request.")

    def _update_buttons(self) -> None:
        recording = self._is_running(self._record_process)
        playing = self._is_running(self._play_process)
        replayable = self._last_bag_path is not None and self._is_bag_directory(self._last_bag_path)

        self.record_button.setEnabled(not recording and not playing)
        self.stop_record_button.setEnabled(recording)
        self.play_button.setEnabled(not recording and not playing and replayable)
        self.stop_play_button.setEnabled(playing)
        self.choose_button.setEnabled(not recording and not playing)
        self.preset_combo.setEnabled(not recording and not playing)

        if recording:
            self.status_label.setText(f"recording: {self._active_preset_name}")
        elif playing:
            self.status_label.setText("replaying")
        else:
            self._update_preset_label()

    def _update_bag_path_display(self) -> None:
        self.bag_path_edit.setText(str(self._last_bag_path or ""))
        self.bag_path_edit.setPlaceholderText(str(self._output_dir))

    def _update_preset_label(self) -> None:
        if not hasattr(self, "status_label"):
            return
        self.status_label.setText(
            f"idle: {self._active_preset_name} ({len(self._active_record_topics())} topics)"
        )

    def _latest_bag_path(self) -> Optional[Path]:
        if not self._output_dir.exists():
            return None
        candidates = [
            path
            for path in self._output_dir.iterdir()
            if path.is_dir() and self._is_bag_directory(path)
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda path: path.stat().st_mtime)

    def _is_bag_directory(self, path: Path) -> bool:
        return path.is_dir() and (path / "metadata.yaml").exists()

    def _close_record_log(self) -> None:
        if self._record_log_file is not None:
            self._record_log_file.close()
            self._record_log_file = None

    def _close_play_log(self) -> None:
        if self._play_log_file is not None:
            self._play_log_file.close()
            self._play_log_file = None

    def _log(self, level: str, message: str) -> None:
        if self._log_callback is not None:
            self._log_callback(level, message)

    def _is_running(self, process: Optional[subprocess.Popen]) -> bool:
        return process is not None and process.poll() is None

    def _unique_topics(self, topics: Iterable[str]) -> list[str]:
        unique = []
        seen = set()
        for topic in topics:
            topic = str(topic).strip()
            if not topic or topic in seen:
                continue
            unique.append(topic)
            seen.add(topic)
        return unique

    def _normalize_presets(
        self,
        record_presets: Optional[dict[str, Iterable[str]]],
        fallback_topics: Iterable[str],
    ) -> dict[str, list[str]]:
        source_presets = record_presets or {}
        normalized = {
            str(name): self._unique_topics(topics)
            for name, topics in source_presets.items()
            if str(name).strip()
        }
        if normalized:
            return normalized
        return {"Custom": self._unique_topics(fallback_topics)}

    def _resolve_default_preset(self, requested: str) -> str:
        if requested and requested in self._record_presets:
            return requested
        if self._record_presets:
            return next(iter(self._record_presets))
        return "Custom"

    def _active_record_topics(self) -> list[str]:
        return self._record_presets.get(self._active_preset_name, [])

    def _slugify(self, value: str) -> str:
        slug = "".join(char.lower() if char.isalnum() else "_" for char in value)
        return "_".join(part for part in slug.split("_") if part) or "record"

    def _default_output_dir(self) -> Path:
        helianthus_dir = Path(__file__).resolve().parents[3]
        return helianthus_dir / "Data" / "gui_rosbags"
