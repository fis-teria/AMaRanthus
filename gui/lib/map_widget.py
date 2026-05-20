import json

from PyQt5.QtWebEngineWidgets import QWebEngineSettings, QWebEngineView
from PyQt5.QtWidgets import QSizePolicy

from .map_html import MAP_HTML


class MapWidget(QWebEngineView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._dark_mode = False

        page = self.page()
        settings = page.settings()
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.PluginsEnabled, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.AllowRunningInsecureContent, False)
        settings.setAttribute(QWebEngineSettings.FullScreenSupportEnabled, False)
        settings.setAttribute(QWebEngineSettings.WebGLEnabled, False)

        self.loadFinished.connect(lambda _: self._apply_theme_to_page())
        self.load_map()

    def load_map(self) -> None:
        self.setHtml(MAP_HTML)

    def search_route(self, start_query: str, end_query: str) -> None:
        script = (
            f"window.searchRouteFromNative({json.dumps(start_query)},"
            f" {json.dumps(end_query)});"
        )
        self.page().runJavaScript(script)

    def set_phone_current(self, point) -> None:
        self._set_phone_point("setPhoneCurrentFromNative", point)

    def set_phone_goal(self, point) -> None:
        self._set_phone_point("setPhoneGoalFromNative", point)

    def set_phone_route(self, points, steps=None) -> None:
        payload = []
        for point in points or []:
            payload.append(
                {
                    "lat": point.lat,
                    "lon": point.lon,
                    "name": point.name,
                }
            )
        step_payload = []
        for step in steps or []:
            step_payload.append(
                {
                    "lat": step.lat,
                    "lon": step.lon,
                    "route_index": step.route_index,
                    "text": step.text,
                    "distance_m": step.distance_m,
                    "duration_sec": step.duration_sec,
                }
            )
        script = (
            "window.setPhoneRouteFromNative && "
            f"window.setPhoneRouteFromNative({json.dumps(payload)}, {json.dumps(step_payload)});"
        )
        self.page().runJavaScript(script)

    def set_dark_mode(self, enabled: bool) -> None:
        self._dark_mode = enabled
        self._apply_theme_to_page()

    def _set_phone_point(self, function_name: str, point) -> None:
        payload = None
        if point is not None:
            payload = {
                "lat": point.lat,
                "lon": point.lon,
                "name": point.name,
                "accuracy_m": point.accuracy_m,
            }
        script = f"window.{function_name} && window.{function_name}({json.dumps(payload)});"
        self.page().runJavaScript(script)

    def _apply_theme_to_page(self) -> None:
        script = f"window.setMapDarkMode && window.setMapDarkMode({str(self._dark_mode).lower()});"
        self.page().runJavaScript(script)
