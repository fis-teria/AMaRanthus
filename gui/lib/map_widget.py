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

    def set_dark_mode(self, enabled: bool) -> None:
        self._dark_mode = enabled
        self._apply_theme_to_page()

    def _apply_theme_to_page(self) -> None:
        script = f"window.setMapDarkMode && window.setMapDarkMode({str(self._dark_mode).lower()});"
        self.page().runJavaScript(script)
