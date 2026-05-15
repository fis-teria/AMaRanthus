from dataclasses import dataclass
from typing import Callable, Optional

from PyQt5.QtCore import QObject, QProcess, QTimer


@dataclass(frozen=True)
class GpuStatus:
    available: bool
    utilization_percent: Optional[int] = None
    memory_used_mib: Optional[int] = None
    memory_total_mib: Optional[int] = None
    temperature_c: Optional[int] = None
    name: str = ""
    error: str = ""


GpuStatusCallback = Callable[[GpuStatus], None]
LogCallback = Callable[[str, str], None]


class GpuMonitor(QObject):
    def __init__(self, interval_sec: float = 1.0, enabled: bool = True, parent=None):
        super().__init__(parent)
        self._interval_ms = max(250, int(float(interval_sec) * 1000))
        self._enabled = enabled
        self._callback: Optional[GpuStatusCallback] = None
        self._log_callback: Optional[LogCallback] = None
        self._last_error = ""
        self._process: Optional[QProcess] = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._timeout_timer = QTimer(self)
        self._timeout_timer.setSingleShot(True)
        self._timeout_timer.timeout.connect(self._kill_stale_process)

    def set_callback(self, callback: Optional[GpuStatusCallback]) -> None:
        self._callback = callback

    def set_log_callback(self, callback: Optional[LogCallback]) -> None:
        self._log_callback = callback

    def start(self) -> None:
        if not self._enabled:
            self._emit(GpuStatus(available=False, error="disabled"))
            return
        self._poll()
        self._timer.start(self._interval_ms)

    def stop(self) -> None:
        self._timer.stop()
        self._timeout_timer.stop()
        if self._process is not None:
            self._process.kill()
            self._process.deleteLater()
            self._process = None

    def _poll(self) -> None:
        if self._process is not None:
            return

        process = QProcess(self)
        process.finished.connect(self._on_process_finished)
        process.errorOccurred.connect(self._on_process_error)
        self._process = process
        process.start(
            "nvidia-smi",
            [
                "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,name",
                "--format=csv,noheader,nounits",
            ],
        )
        self._timeout_timer.start(2500)

    def _on_process_finished(self, exit_code: int, _exit_status) -> None:
        process = self._process
        if process is None:
            return

        self._timeout_timer.stop()
        stdout = bytes(process.readAllStandardOutput()).decode("utf-8", errors="replace")
        stderr = bytes(process.readAllStandardError()).decode("utf-8", errors="replace")
        process.deleteLater()
        self._process = None

        if exit_code != 0:
            self._emit_error(stderr.strip() or f"nvidia-smi exit code {exit_code}")
            return

        line = stdout.strip().splitlines()[0] if stdout.strip() else ""
        if not line:
            self._emit_error("empty nvidia-smi output")
            return

        try:
            util, mem_used, mem_total, temp, name = [part.strip() for part in line.split(",", 4)]
            self._last_error = ""
            self._emit(
                GpuStatus(
                    available=True,
                    utilization_percent=int(float(util)),
                    memory_used_mib=int(float(mem_used)),
                    memory_total_mib=int(float(mem_total)),
                    temperature_c=int(float(temp)),
                    name=name,
                )
            )
        except (ValueError, IndexError) as exc:
            self._emit_error(f"parse error: {exc}")

    def _on_process_error(self, error) -> None:
        if self._process is not None:
            self._process.deleteLater()
            self._process = None
        self._timeout_timer.stop()
        self._emit_error(f"QProcess error {int(error)}")

    def _kill_stale_process(self) -> None:
        if self._process is None:
            return
        self._process.kill()
        self._process.deleteLater()
        self._process = None
        self._emit_error("nvidia-smi timeout")

    def _emit_error(self, error: str) -> None:
        if error != self._last_error:
            self._last_error = error
            if self._log_callback is not None:
                self._log_callback("WARN", f"GPU monitor unavailable: {error}")
        self._emit(GpuStatus(available=False, error=error))

    def _emit(self, status: GpuStatus) -> None:
        if self._callback is not None:
            self._callback(status)
