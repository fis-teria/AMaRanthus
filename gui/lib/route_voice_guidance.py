import json
import math
import threading
from collections import deque
from typing import Callable, Optional
from urllib.error import URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from PyQt5.QtCore import QObject, QUrl, pyqtSignal

from .models import GeoPoint, RouteStep

try:
    from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer
except ImportError:  # pragma: no cover - depends on the local Qt install.
    QMediaContent = None
    QMediaPlayer = None


LogCallback = Callable[[str, str], None]


class RouteVoiceGuidance(QObject):
    _audio_ready = pyqtSignal(str)
    _log_signal = pyqtSignal(str, str)

    def __init__(
        self,
        *,
        enabled: bool,
        backend_url: str,
        preannounce_distance_m: float,
        early_preannounce_distance_m: float = 1000.0,
        request_timeout_sec: float = 300.0,
        parent=None,
    ):
        super().__init__(parent)
        self._enabled = bool(enabled)
        self._backend_url = backend_url.rstrip("/") + "/"
        self._preannounce_distance_m = max(1.0, float(preannounce_distance_m))
        self._early_preannounce_distance_m = max(
            self._preannounce_distance_m,
            float(early_preannounce_distance_m),
        )
        self._request_timeout_sec = max(1.0, float(request_timeout_sec))
        self._log_callback: Optional[LogCallback] = None
        self._route_signature = ""
        self._last_next_step_key: Optional[str] = None
        self._progress_announced: set[str] = set()
        self._early_preannounced: set[str] = set()
        self._preannounced: set[str] = set()
        self._request_queue: deque[dict] = deque(maxlen=8)
        self._request_in_flight = False
        self._queue_lock = threading.Lock()
        self._audio_queue: deque[str] = deque(maxlen=8)

        self._player = None
        self._audio_ready.connect(self._enqueue_audio)
        self._log_signal.connect(self._dispatch_log)
        if self._enabled:
            if QMediaPlayer is None or QMediaContent is None:
                self._enabled = False
                self._log("WARN", "Route voice guidance disabled: PyQt5.QtMultimedia is unavailable")
            else:
                self._player = QMediaPlayer(self)
                self._player.stateChanged.connect(self._on_player_state_changed)
                self._log(
                    "INFO",
                    (
                        "Route voice guidance enabled: "
                        f"backend={self._backend_url}, "
                        f"early_preannounce={self._early_preannounce_distance_m:.0f}m, "
                        f"preannounce={self._preannounce_distance_m:.0f}m"
                    ),
                )

    def set_log_callback(self, callback: Optional[LogCallback]) -> None:
        self._log_callback = callback

    def stop(self) -> None:
        if self._player is not None:
            self._player.stop()

    def update_route(
        self,
        *,
        current: Optional[GeoPoint],
        route_points: list[GeoPoint],
        route_steps: list[RouteStep],
    ) -> None:
        if not self._enabled or current is None or len(route_points) < 2 or not route_steps:
            return

        route_signature = self._build_route_signature(route_points, route_steps)
        if route_signature != self._route_signature:
            self._route_signature = route_signature
            self._last_next_step_key = None
            self._progress_announced.clear()
            self._early_preannounced.clear()
            self._preannounced.clear()
            self._log("INFO", "Route voice guidance state reset for new route")

        current_index = self._nearest_route_index(current, route_points)
        next_step = self._next_step(route_steps, current_index)
        if next_step is None:
            return

        step_key = self._step_key(next_step)
        dist_to_step_m = self._distance_along_route(route_points, current_index, next_step.route_index)

        announced_progress = False
        if step_key != self._last_next_step_key and step_key not in self._progress_announced:
            self._last_next_step_key = step_key
            self._progress_announced.add(step_key)
            self._enqueue_guidance_request(next_step, dist_to_step_m, reason="next_step")
            announced_progress = True

        should_early_preannounce = (
            not announced_progress
            and step_key not in self._early_preannounced
            and next_step.route_index > current_index
            and self._preannounce_distance_m < dist_to_step_m <= self._early_preannounce_distance_m
        )
        if should_early_preannounce:
            self._early_preannounced.add(step_key)
            self._enqueue_guidance_request(next_step, dist_to_step_m, reason="early_preannounce")

        should_preannounce = (
            not announced_progress
            and not should_early_preannounce
            and step_key not in self._preannounced
            and next_step.route_index > current_index
            and 0.0 < dist_to_step_m <= self._preannounce_distance_m
        )
        if should_preannounce:
            self._preannounced.add(step_key)
            self._enqueue_guidance_request(next_step, dist_to_step_m, reason="preannounce")

    def _enqueue_guidance_request(self, step: RouteStep, distance_m: float, *, reason: str) -> None:
        payload = {
            "step": {
                "text": step.text,
                "route_index": step.route_index,
                "distance_m": step.distance_m,
                "duration_sec": step.duration_sec,
            },
            "distance_m": max(0.0, distance_m),
            "source": "route_guidance",
        }
        with self._queue_lock:
            self._request_queue.append(payload)
            if self._request_in_flight:
                return
            self._request_in_flight = True
        self._log("INFO", f"Queued route voice guidance ({reason}): {step.text}")
        threading.Thread(
            target=self._request_worker,
            name="amaranthus-route-voice-guidance",
            daemon=True,
        ).start()

    def _request_worker(self) -> None:
        while True:
            with self._queue_lock:
                if not self._request_queue:
                    self._request_in_flight = False
                    return
                payload = self._request_queue.popleft()

            try:
                audio_url = self._synthesize_route_guidance(payload)
            except Exception as exc:
                self._log("WARN", f"Route voice guidance synthesis failed: {type(exc).__name__}: {exc}")
                continue

            if audio_url:
                self._audio_ready.emit(audio_url)

    def _synthesize_route_guidance(self, payload: dict) -> str:
        request = Request(
            urljoin(self._backend_url, "api/route_guidance"),
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self._request_timeout_sec) as response:
                result = json.loads(response.read().decode("utf-8"))
        except URLError as exc:
            raise RuntimeError(f"backend unavailable at {self._backend_url}: {exc}") from exc

        if not result.get("ok", True) and result.get("error"):
            raise RuntimeError(str(result["error"]))
        audio_url = str(result.get("audio_url") or "").strip()
        if not audio_url:
            raise RuntimeError("backend response did not include audio_url")
        return urljoin(self._backend_url, audio_url.lstrip("/"))

    def _enqueue_audio(self, audio_url: str) -> None:
        self._audio_queue.append(audio_url)
        self._play_next_audio()

    def _play_next_audio(self) -> None:
        if self._player is None or not self._audio_queue:
            return
        if self._player.state() == QMediaPlayer.PlayingState:
            return
        audio_url = self._audio_queue.popleft()
        self._player.setMedia(QMediaContent(QUrl(audio_url)))
        self._player.play()
        self._log("INFO", f"Playing route voice guidance: {audio_url}")

    def _on_player_state_changed(self, state: int) -> None:
        if QMediaPlayer is not None and state == QMediaPlayer.StoppedState:
            self._play_next_audio()

    def _build_route_signature(
        self,
        route_points: list[GeoPoint],
        route_steps: list[RouteStep],
    ) -> str:
        first = route_points[0]
        last = route_points[-1]
        step_bits = [
            f"{step.route_index}:{step.text}:{step.lat:.6f}:{step.lon:.6f}"
            for step in route_steps[:20]
        ]
        return "|".join(
            [
                str(len(route_points)),
                f"{first.lat:.6f},{first.lon:.6f}",
                f"{last.lat:.6f},{last.lon:.6f}",
                ";".join(step_bits),
            ]
        )

    def _nearest_route_index(self, current: GeoPoint, route_points: list[GeoPoint]) -> int:
        best_index = 0
        best_distance = float("inf")
        for index, point in enumerate(route_points):
            distance = self._distance_m(current, point)
            if distance < best_distance:
                best_distance = distance
                best_index = index
        return best_index

    def _next_step(self, route_steps: list[RouteStep], current_index: int) -> Optional[RouteStep]:
        for step in route_steps:
            if step.route_index >= current_index:
                return step
        return route_steps[-1] if route_steps else None

    def _distance_along_route(
        self,
        route_points: list[GeoPoint],
        from_index: int,
        to_index: int,
    ) -> float:
        start = max(0, min(from_index, len(route_points) - 1))
        end = max(0, min(to_index, len(route_points) - 1))
        if end <= start:
            return 0.0
        total = 0.0
        for index in range(start, end):
            total += self._distance_m(route_points[index], route_points[index + 1])
        return total

    def _step_key(self, step: RouteStep) -> str:
        return f"{step.route_index}:{step.lat:.6f}:{step.lon:.6f}:{step.text}"

    def _distance_m(self, a: GeoPoint, b: GeoPoint) -> float:
        mean_lat = math.radians((a.lat + b.lat) * 0.5)
        dy = (b.lat - a.lat) * 111_320.0
        dx = (b.lon - a.lon) * 111_320.0 * math.cos(mean_lat)
        return math.hypot(dx, dy)

    def _log(self, level: str, message: str) -> None:
        self._log_signal.emit(level, message)

    def _dispatch_log(self, level: str, message: str) -> None:
        if self._log_callback is not None:
            self._log_callback(level, message)
        else:
            print(f"[{level}] {message}")
