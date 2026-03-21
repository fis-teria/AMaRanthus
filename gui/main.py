# -*- coding: utf-8 -*-
import math
import random
import sys
import os
from dataclasses import dataclass
from typing import List

from PyQt5.QtCore import Qt, QTimer, QRectF, QPointF, QUrl, QLocale
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPolygonF
from PyQt5.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings


# =========================
# データ定義
# =========================
@dataclass
class DetectedObject:
    x_m: float      # 自車中心ローカル座標 [m] 右+
    y_m: float      # 自車中心ローカル座標 [m] 前+
    kind: str       # "person" or "car"


# =========================
# 左: Googleマップ表示
# =========================
class MapWidget(QWebEngineView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Qt WebEngineの設定（日本語入力対応）
        page = self.page()
        settings = page.settings()
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.PluginsEnabled, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.AllowRunningInsecureContent, False)

        # IMEサポート強化
        settings.setAttribute(QWebEngineSettings.FullScreenSupportEnabled, False)  # 不要な機能を無効化
        settings.setAttribute(QWebEngineSettings.WebGLEnabled, False)  # WebGL無効化でパフォーマンス向上

        self.load_map()

    def load_map(self):
        # OpenStreetMap + Leaflet + Routing + Search を使用（APIキー不要・無料）
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>OpenStreetMap with Search & Routing</title>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
            <link rel="stylesheet" href="https://unpkg.com/leaflet-routing-machine@3.2.12/dist/leaflet-routing-machine.css" />
            <link rel="stylesheet" href="https://unpkg.com/leaflet-control-geocoder@2.4.0/dist/Control.Geocoder.css" />
            <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
            <script src="https://unpkg.com/leaflet-routing-machine@3.2.12/dist/leaflet-routing-machine.js"></script>
            <script src="https://unpkg.com/leaflet-control-geocoder@2.4.0/dist/Control.Geocoder.js"></script>
            <style>
                #map {
                    height: 100vh;
                    width: 100%;
                }
                html, body {
                    height: 100%;
                    margin: 0;
                    padding: 0;
                }
                .search-container {
                    position: absolute;
                    top: 10px;
                    left: 10px;
                    z-index: 1000;
                    background: white;
                    padding: 15px;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.2);
                    font-family: 'Noto Sans CJK JP', Arial, sans-serif;
                    min-width: 300px;
                }
                .search-container h4 {
                    margin: 0 0 10px 0;
                    color: #333;
                    font-size: 14px;
                }
                .search-input {
                    width: 100%;
                    padding: 8px;
                    margin-bottom: 8px;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    font-size: 14px;
                    font-family: 'Noto Sans CJK JP', 'IPAGothic', 'TakaoGothic', 'Yu Gothic', 'MS Gothic', Arial, sans-serif;
                }
                .search-button {
                    width: 100%;
                    padding: 8px;
                    background: #4285f4;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                    font-size: 14px;
                }
                .search-button:hover {
                    background: #3367d6;
                }
                .search-button:disabled {
                    background: #ccc;
                    cursor: not-allowed;
                }
                .route-info {
                    position: absolute;
                    top: 10px;
                    right: 10px;
                    background: white;
                    padding: 10px;
                    border-radius: 5px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.2);
                    z-index: 1000;
                    font-family: 'Noto Sans CJK JP', Arial, sans-serif;
                    font-size: 12px;
                    max-width: 250px;
                    display: none;
                }
                .route-info.show {
                    display: block;
                }
                .leaflet-control-attribution {
                    font-size: 10px;
                }
            </style>
        </head>
        <body>
            <div id="map"></div>

            <!-- 検索コンテナ -->
            <div class="search-container">
                <h4>ルート検索</h4>
                <input type="text" id="start-search" class="search-input" placeholder="出発地を入力（例: 東京駅）" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" lang="ja" inputmode="text">
                <input type="text" id="end-search" class="search-input" placeholder="目的地を入力（例: 渋谷駅）" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" lang="ja" inputmode="text">
                <button id="search-route" class="search-button">ルート検索</button>
            </div>

            <!-- ルート情報 -->
            <div class="route-info" id="route-info">
                <h4>ルート情報</h4>
                <p id="route-distance">距離: -- km</p>
                <p id="route-time">時間: -- 分</p>
            </div>

            <script>
                // 東京駅を中心とした初期位置
                const tokyoStation = [35.681236, 139.767125];

                // マップの作成
                const map = L.map('map').setView(tokyoStation, 13);

                // OpenStreetMap タイルレイヤー
                L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
                    maxZoom: 19,
                }).addTo(map);

                // 変数定義
                let startMarker = null;
                let endMarker = null;
                let routingControl = null;
                let startCoords = null;
                let endCoords = null;

                // Geocoder（住所検索）インスタンス
                const geocoder = L.Control.Geocoder.nominatim();

                // 検索関数
                function searchLocation(query, callback) {
                    geocoder.geocode(query, function(results) {
                        if (results && results.length > 0) {
                            const result = results[0];
                            callback({
                                lat: result.center.lat,
                                lng: result.center.lng,
                                name: result.name
                            });
                        } else {
                            alert('場所が見つかりませんでした: ' + query);
                        }
                    });
                }

                // マーカー設置関数
                function setMarker(coords, type) {
                    // 既存マーカーを削除
                    if (type === 'start' && startMarker) {
                        map.removeLayer(startMarker);
                    }
                    if (type === 'end' && endMarker) {
                        map.removeLayer(endMarker);
                    }

                    const marker = L.marker([coords.lat, coords.lng])
                        .addTo(map)
                        .bindPopup('<b>' + (type === 'start' ? '出発地' : '目的地') + '</b><br/>' + coords.name)
                        .openPopup();

                    if (type === 'start') {
                        startMarker = marker;
                        startCoords = coords;
                    } else {
                        endMarker = marker;
                        endCoords = coords;
                    }

                    // マップの中心を調整
                    if (startCoords && endCoords) {
                        const bounds = L.latLngBounds([startCoords.lat, startCoords.lng], [endCoords.lat, endCoords.lng]);
                        map.fitBounds(bounds, { padding: [20, 20] });
                    } else {
                        map.setView([coords.lat, coords.lng], 15);
                    }
                }

                // ルート検索関数
                function calculateRoute() {
                    if (!startCoords || !endCoords) {
                        alert('出発地と目的地の両方を設定してください。');
                        return;
                    }

                    // 既存のルートを削除
                    if (routingControl) {
                        map.removeControl(routingControl);
                    }

                    // OpenRouteServiceを使用したルート検索
                    routingControl = L.Routing.control({
                        waypoints: [
                            L.latLng(startCoords.lat, startCoords.lng),
                            L.latLng(endCoords.lat, endCoords.lng)
                        ],
                        routeWhileDragging: false,
                        createMarker: function() { return null; }, // カスタムマーカー使用のため
                        router: L.Routing.openrouteservice({
                            serviceUrl: 'https://api.openrouteservice.org/v2/directions/',
                            profile: 'driving-car',
                            api_key: null, // 無料枠使用（APIキー不要）
                            timeout: 30 * 1000,
                        }),
                        formatter: new L.Routing.Formatter({
                            language: 'ja'
                        }),
                        summaryTemplate: '<h3>{name}</h3><p>{distance}, {time}</p>',
                    }).addTo(map);

                    // ルート計算完了時のイベント
                    routingControl.on('routesfound', function(e) {
                        const routes = e.routes;
                        const summary = routes[0].summary;

                        // ルート情報を表示
                        const routeInfo = document.getElementById('route-info');
                        const distanceKm = (summary.totalDistance / 1000).toFixed(1);
                        const timeMin = Math.round(summary.totalTime / 60);

                        document.getElementById('route-distance').textContent = '距離: ' + distanceKm + ' km';
                        document.getElementById('route-time').textContent = '時間: ' + timeMin + ' 分';
                        routeInfo.classList.add('show');

                        console.log('ルート検索完了:', summary);
                    });

                    // エラー時のイベント
                    routingControl.on('routingerror', function(e) {
                        console.error('ルート検索エラー:', e.error);
                        alert('ルート検索に失敗しました。ネットワーク接続を確認してください。');
                    });
                }

                // IMEイベント処理（日本語入力対応）
                function setupIMEHandling(inputElement) {
                    let isComposing = false;

                    inputElement.addEventListener('compositionstart', function(e) {
                        isComposing = true;
                        console.log('IME composition started');
                    });

                    inputElement.addEventListener('compositionend', function(e) {
                        isComposing = false;
                        console.log('IME composition ended:', e.data);
                        // IME確定時の処理（自動検索は無効化）
                        // performGeocoding(inputElement.id, e.data.trim());
                    });

                    inputElement.addEventListener('input', function(e) {
                        if (!isComposing) {
                            // IME確定済みの入力の場合
                            console.log('Direct input:', e.target.value);
                        }
                    });

                    inputElement.addEventListener('keydown', function(e) {
                        // IME切り替えキー（半角/全角キー）の処理
                        if (e.key === 'Convert' || e.key === 'NonConvert' || e.key === 'KanaMode') {
                            console.log('IME toggle key pressed:', e.key);
                        }
                    });

                    // フォーカス時のIMEモード設定
                    inputElement.addEventListener('focus', function(e) {
                        // Qt WebEngineにIMEモードを通知（APIが存在しないため無効化）
                        // if (window.qt && window.qt.webEngine) {
                        //     try {
                        //         window.qt.webEngine.setInputMethodHints(0);
                        //     } catch (error) {
                        //         console.log('Qt WebEngine IME hint setting failed:', error);
                        //     }
                        // }
                    });
                }

                // 両方の検索入力フィールドにIME処理を設定
                setupIMEHandling(document.getElementById('start-search'));
                setupIMEHandling(document.getElementById('end-search'));

                // 検索ボタンのイベントリスナー
                document.getElementById('search-route').addEventListener('click', function() {
                    const startQuery = document.getElementById('start-search').value.trim();
                    const endQuery = document.getElementById('end-search').value.trim();

                    if (!startQuery || !endQuery) {
                        alert('出発地と目的地の両方を入力してください。');
                        return;
                    }

                    // ボタンを無効化
                    this.disabled = true;
                    this.textContent = '検索中...';

                    // 出発地検索
                    searchLocation(startQuery, function(startResult) {
                        setMarker(startResult, 'start');

                        // 目的地検索
                        searchLocation(endQuery, function(endResult) {
                            setMarker(endResult, 'end');

                            // ルート検索実行
                            setTimeout(calculateRoute, 500);

                            // ボタンを有効化
                            document.getElementById('search-route').disabled = false;
                            document.getElementById('search-route').textContent = 'ルート検索';
                        });
                    });
                });

                // Enterキーでも検索可能
                document.getElementById('start-search').addEventListener('keypress', function(e) {
                    if (e.key === 'Enter') {
                        document.getElementById('search-route').click();
                    }
                });
                document.getElementById('end-search').addEventListener('keypress', function(e) {
                    if (e.key === 'Enter') {
                        document.getElementById('search-route').click();
                    }
                });

                // スケールコントロール追加
                L.control.scale().addTo(map);

                // 初期マーカー（東京駅）
                const initialMarker = L.marker(tokyoStation)
                    .addTo(map)
                    .bindPopup('<b>東京駅</b><br/>検索ボックスでルート検索ができます')
                    .openPopup();

                // 日本語入力対応のための設定
                document.addEventListener('DOMContentLoaded', function() {
                    const inputs = document.querySelectorAll('.search-input');
                    inputs.forEach(function(input) {
                        input.style.fontFamily = "'Noto Sans CJK JP', 'IPAGothic', 'TakaoGothic', 'Yu Gothic', 'MS Gothic', Arial, sans-serif";
                        input.setAttribute('lang', 'ja');
                        input.setAttribute('inputmode', 'text');
                        input.addEventListener('focus', function() {
                            // IMEが有効になるようにする
                            this.style.imeMode = 'active';
                        });
                    });
                });
            </script>
        </body>
        </html>
        """
        self.setHtml(html_content)


# =========================
# 右上: ステータス表示
# =========================
class StatusPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)

        layout = QGridLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setHorizontalSpacing(16)
        layout.setVerticalSpacing(10)

        # 日本語フォント設定
        jp_font = QFont()
        jp_font.setFamily("Noto Sans CJK JP, IPAGothic, TakaoGothic, Yu Gothic, MS Gothic, Arial")
        jp_font.setPointSize(10)

        self.labels = {}
        items = [
            ("車速", "-- km/h"),
            ("前方最短距離", "-- m"),
            ("検知人数", "--"),
            ("検知車両数", "--"),
            ("モード", "--"),
            ("GPS", "--"),
        ]

        for row, (title, value) in enumerate(items):
            title_label = QLabel(title)
            value_label = QLabel(value)
            title_label.setFont(jp_font)
            value_label.setFont(jp_font)
            title_label.setStyleSheet("font-weight: bold;")
            value_label.setStyleSheet("font-size: 18px;")
            layout.addWidget(title_label, row, 0)
            layout.addWidget(value_label, row, 1)
            self.labels[title] = value_label

    def update_status(
        self,
        speed_kmh: float,
        min_distance_m: float,
        person_count: int,
        car_count: int,
        mode: str,
        gps_status: str,
    ) -> None:
        self.labels["車速"].setText(f"{speed_kmh:.1f} km/h")
        self.labels["前方最短距離"].setText(f"{min_distance_m:.2f} m")
        self.labels["検知人数"].setText(str(person_count))
        self.labels["検知車両数"].setText(str(car_count))
        self.labels["モード"].setText(mode)
        self.labels["GPS"].setText(gps_status)


# =========================
# 右下: LaserScan可視化
# =========================
class SensorView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(500, 500)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # 表示レンジ [m]
        self.max_range_m = 20.0

        # ダミーデータ
        self.scan_points: List[QPointF] = []
        self.objects: List[DetectedObject] = []
        self.speed_kmh = 0.0
        self.min_distance_m = 99.0

    def set_data(
        self,
        scan_xy_m: List[QPointF],
        objects: List[DetectedObject],
        speed_kmh: float,
        min_distance_m: float,
    ) -> None:
        self.scan_points = scan_xy_m
        self.objects = objects
        self.speed_kmh = speed_kmh
        self.min_distance_m = min_distance_m
        self.update()

    def meter_to_view(self, x_m: float, y_m: float) -> QPointF:
        """
        自車中心ローカル座標(m) -> ウィジェット座標(px)
        x: 右+
        y: 前+
        """
        w = self.width()
        h = self.height()

        # 自車を下側中央に置く
        origin_x = w * 0.5
        origin_y = h * 0.82

        scale = min(w * 0.42, h * 0.72) / self.max_range_m

        px = origin_x + x_m * scale
        py = origin_y - y_m * scale
        return QPointF(px, py)

    def draw_grid(self, painter: QPainter) -> None:
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        # 日本語フォント設定
        jp_font = QFont()
        jp_font.setFamily("Noto Sans CJK JP, IPAGothic, TakaoGothic, Yu Gothic, MS Gothic, Arial")
        painter.setFont(jp_font)

        # 背景
        painter.fillRect(self.rect(), QColor(18, 18, 22))

        # 同心円風の距離ガイド
        pen = QPen(QColor(70, 70, 80))
        pen.setWidth(1)
        painter.setPen(pen)

        for dist in [5, 10, 15, 20]:
            center = self.meter_to_view(0.0, 0.0)
            edge = self.meter_to_view(dist, 0.0)
            radius = abs(edge.x() - center.x())
            rect = QRectF(
                center.x() - radius,
                center.y() - radius,
                radius * 2,
                radius * 2,
            )
            painter.drawEllipse(rect)

        # 前方軸
        axis_pen = QPen(QColor(90, 120, 255))
        axis_pen.setWidth(2)
        painter.setPen(axis_pen)
        p0 = self.meter_to_view(0.0, 0.0)
        p1 = self.meter_to_view(0.0, self.max_range_m)
        painter.drawLine(p0, p1)

        # 横軸
        side_pen = QPen(QColor(70, 70, 90))
        side_pen.setWidth(1)
        painter.setPen(side_pen)
        l = self.meter_to_view(-self.max_range_m, 0.0)
        r = self.meter_to_view(self.max_range_m, 0.0)
        painter.drawLine(l, r)

        # 危険エリア（前方扇形）
        danger_brush = QBrush(QColor(255, 80, 80, 40))
        painter.setBrush(danger_brush)
        painter.setPen(Qt.NoPen)

        origin = self.meter_to_view(0.0, 0.0)
        left = self.meter_to_view(-1.8, 6.0)
        right = self.meter_to_view(1.8, 6.0)
        poly = QPolygonF([origin, left, right])
        painter.drawPolygon(poly)

        painter.restore()

    def draw_vehicle(self, painter: QPainter) -> None:
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        center = self.meter_to_view(0.0, 0.0)
        body = QPolygonF(
            [
                QPointF(center.x(), center.y() - 18),
                QPointF(center.x() - 14, center.y() + 16),
                QPointF(center.x() + 14, center.y() + 16),
            ]
        )

        painter.setBrush(QBrush(QColor(80, 200, 255)))
        painter.setPen(QPen(QColor(220, 240, 255), 2))
        painter.drawPolygon(body)

        painter.restore()

    def draw_scan(self, painter: QPainter) -> None:
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        pen = QPen(QColor(0, 255, 170))
        pen.setWidth(3)
        painter.setPen(pen)

        for p_m in self.scan_points:
            p = self.meter_to_view(p_m.x(), p_m.y())
            painter.drawPoint(p)

        painter.restore()

    def draw_objects(self, painter: QPainter) -> None:
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        for obj in self.objects:
            p = self.meter_to_view(obj.x_m, obj.y_m)

            if obj.kind == "person":
                painter.setBrush(QBrush(QColor(0, 220, 120)))
                painter.setPen(QPen(QColor(220, 255, 220), 2))
                painter.drawEllipse(p, 9, 9)
                painter.drawText(p + QPointF(10, -10), "Person")
            elif obj.kind == "car":
                painter.setBrush(QBrush(QColor(255, 170, 40)))
                painter.setPen(QPen(QColor(255, 240, 210), 2))
                rect = QRectF(p.x() - 12, p.y() - 7, 24, 14)
                painter.drawRect(rect)
                painter.drawText(p + QPointF(14, -8), "Car")

        painter.restore()

    def draw_overlay_text(self, painter: QPainter) -> None:
        painter.save()
        painter.setPen(QColor(230, 230, 230))
        
        # 日本語フォント設定
        jp_font = QFont()
        jp_font.setFamily("Noto Sans CJK JP, IPAGothic, TakaoGothic, Yu Gothic, MS Gothic, Arial")
        jp_font.setPointSize(11)
        painter.setFont(jp_font)

        painter.drawText(12, 24, "右画面: 自車中心 LaserScan / 検知物体ビュー")
        painter.drawText(12, 46, f"表示レンジ: {self.max_range_m:.0f} m")
        painter.drawText(12, 68, f"最短距離: {self.min_distance_m:.2f} m")

        painter.restore()

    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QPainter(self)
        self.draw_grid(painter)
        self.draw_scan(painter)
        self.draw_objects(painter)
        self.draw_vehicle(painter)
        self.draw_overlay_text(painter)


# =========================
# メインウィンドウ
# =========================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Robot UI Sample")
        self.resize(1500, 850)

        splitter = QSplitter(Qt.Horizontal)

        # 左
        self.map_widget = MapWidget()

        # 右
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(6, 6, 6, 6)
        right_layout.setSpacing(6)

        self.status_panel = StatusPanel()
        self.sensor_view = SensorView()

        right_layout.addWidget(self.status_panel, 0)
        right_layout.addWidget(self.sensor_view, 1)

        splitter.addWidget(self.map_widget)
        splitter.addWidget(right_container)
        splitter.setSizes([850, 650])

        self.setCentralWidget(splitter)

        # ダミーデータ更新タイマ
        self.t = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_demo_data)
        self.timer.start(100)  # 10Hz

    def generate_fake_scan(self) -> List[QPointF]:
        points = []
        angles_deg = range(-90, 91, 2)

        for ang_deg in angles_deg:
            ang = math.radians(ang_deg)

            # 基本距離
            dist = 12.0 + 1.2 * math.sin(self.t * 0.7 + ang * 2.0)

            # 前方に障害物っぽい塊を作る
            if -12 <= ang_deg <= 8:
                dist = min(dist, 4.0 + 0.5 * math.sin(self.t * 2.0))
            if 25 <= ang_deg <= 38:
                dist = min(dist, 7.0 + 0.4 * math.cos(self.t * 1.5))
            if -40 <= ang_deg <= -30:
                dist = min(dist, 9.0 + 0.2 * math.sin(self.t * 1.3))

            # ノイズ
            dist += random.uniform(-0.08, 0.08)
            dist = max(0.5, min(20.0, dist))

            # 極座標 -> 直交座標
            x = dist * math.sin(ang)
            y = dist * math.cos(ang)
            points.append(QPointF(x, y))

        return points

    def generate_fake_objects(self) -> List[DetectedObject]:
        person_x = 1.5 * math.sin(self.t * 0.8)
        person_y = 5.5 + 0.4 * math.sin(self.t * 1.3)

        car_x = -2.8 + 0.4 * math.cos(self.t * 0.6)
        car_y = 10.0 + 0.3 * math.sin(self.t * 0.9)

        return [
            DetectedObject(x_m=person_x, y_m=person_y, kind="person"),
            DetectedObject(x_m=car_x, y_m=car_y, kind="car"),
        ]

    def compute_min_distance(self, scan_points: List[QPointF]) -> float:
        # 前方かつ左右ある程度の範囲だけ見る簡易例
        dists = []
        for p in scan_points:
            if abs(p.x()) < 2.5 and p.y() > 0.0:
                dists.append(math.hypot(p.x(), p.y()))
        return min(dists) if dists else 99.0

    def update_demo_data(self) -> None:
        self.t += 0.1

        scan_points = self.generate_fake_scan()
        objects = self.generate_fake_objects()
        min_distance = self.compute_min_distance(scan_points)
        speed_kmh = 8.0 + 2.5 * math.sin(self.t * 0.7)

        person_count = sum(1 for o in objects if o.kind == "person")
        car_count = sum(1 for o in objects if o.kind == "car")

        self.status_panel.update_status(
            speed_kmh=speed_kmh,
            min_distance_m=min_distance,
            person_count=person_count,
            car_count=car_count,
            mode="AUTO",
            gps_status="FIX",
        )

        self.sensor_view.set_data(
            scan_xy_m=scan_points,
            objects=objects,
            speed_kmh=speed_kmh,
            min_distance_m=min_distance,
        )


def main():
    # 日本語表示と入力のための環境設定
    os.environ['QT_QPA_PLATFORMTHEME'] = 'gtk2'
    os.environ['LANG'] = 'ja_JP.UTF-8'
    os.environ['LC_ALL'] = 'ja_JP.UTF-8'
    os.environ['QT_IM_MODULE'] = 'ibus'  # または 'fcitx' など、使用しているIMEに合わせて
    os.environ['XMODIFIERS'] = '@im=ibus'

    # QApplication初期化前にロケール設定
    QLocale.setDefault(QLocale(QLocale.Japanese, QLocale.Japan))

    # 高DPI対応（QApplication作成前に設定）
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    # Qt WebEngineのインポート（QApplication作成前に）
    from PyQt5.QtWebEngineWidgets import QWebEngineSettings

    app = QApplication(sys.argv)

    # 日本語入力対応
    app.setAttribute(Qt.AA_DontCreateNativeWidgetSiblings, True)

    # Qt WebEngineの設定（QApplication作成後に設定）
    QWebEngineSettings.globalSettings().setAttribute(QWebEngineSettings.PluginsEnabled, True)
    QWebEngineSettings.globalSettings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
    QWebEngineSettings.globalSettings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
    # IMEサポートのための追加設定
    QWebEngineSettings.globalSettings().setAttribute(QWebEngineSettings.AllowWindowActivationFromJavaScript, True)
    QWebEngineSettings.globalSettings().setAttribute(QWebEngineSettings.JavascriptCanAccessClipboard, True)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()