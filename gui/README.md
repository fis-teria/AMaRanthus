# Robot UI Sample

ロボット用のGUIサンプルアプリケーションです。

## 機能

- **地図表示**: OpenStreetMap + Leafletを使用（APIキー不要・無料）
- **ルート検索**: OpenRouteServiceを使用（APIキー不要・無料）
- GUI 内ボタンによる項目別 Demo / ROS2 データソース切り替え
- ステータス表示（車速、前方最短距離、障害物数、モード、GPS）
- shadow-mode メトリクス表示（操舵差分、曲率差分、warning / intervention score など）
- レーザースキャンデータの可視化
- lane / road edge のオーバーレイ表示
- 検知された obstacle マーカー表示
- GUI内ボタンによるROS bag録画・再生（点群、カメラ画像、Odometry/GPS、TF）
- ダーク / ライトテーマ切り替え

## 地図について

このアプリケーションでは、**OpenStreetMap** と **Leaflet** を使用して地図を表示しています。

### OpenStreetMapの特徴:
- ✅ **完全に無料** - APIキー不要
- ✅ **オープンソース** - 誰でも利用可能
- ✅ **全世界対応** - 世界中の地図データ
- ✅ **コミュニティ運営** - ボランティアによる更新
- ✅ **オフライン対応可能** - タイルデータをキャッシュ可能

### Google Mapsとの比較:
| 機能 | OpenStreetMap + Leaflet | Google Maps |
|------|-------------------------|-------------|
| 料金 | 無料 | 有料（クレジットカード登録必須） |
| APIキー | 不要 | 必須 |
| ストリートビュー | ❌ | ✅ |
| 衛星写真 | 限定的 | ✅ |
| リアルタイム交通情報 | ❌ | ✅ |
| ルート検索 | プラグインで可能 | ✅ |
| 営業時間情報 | ❌ | ✅ |

## セットアップ

### 1. 依存関係のインストール

```bash
uv sync
```

Ubuntu / WSL では、ルートの `setup/ubuntu_setup.sh` を使うと `uv` と `ibus-mozc` もまとめてセットアップできます。

```bash
./setup/ubuntu_setup.sh
```

### ROS2 モード（オプション）

ROS2 トピックを読み込む場合は、別途 ROS2 環境のセットアップが必要です。

**ROS2がインストール済みの場合:**

```bash
# ROS2環境を有効化後、このプロジェクトのvenvでROS2パッケージをインストール
source /opt/ros/humble/setup.bash  # または適切なROS2バージョン
uv pip install rclpy sensor-msgs std-msgs
```

**またはcolconでビルド:**

```bash
cd /path/to/ros2_ws
colcon build --packages-select <このプロジェクト>
```

インストール確認:

```bash
uv pip list | grep -E 'rclpy|sensor-msgs|std-msgs'
```

### 2. 実行

```bash
uv run main.py
```

ワークスペース直下から簡単に起動したい場合は、起動スクリプトも使えます。

```bash
./gui/run_gui.sh
```

`gui/run_gui.sh` は既定で `src/tts/irodori_tts_lite` の HTTP backend も起動します。既に `127.0.0.1:8766` で起動済みなら再利用し、スクリプトが起動した backend は GUI 終了時に停止します。TTS 環境が未セットアップの場合は警告だけ出して GUI 起動は継続します。

```bash
ENABLE_IRODORI_TTS_BACKEND=0 ./gui/run_gui.sh
IRODORI_TTS_BACKEND_PORT=8767 ./gui/run_gui.sh
IRODORI_TTS_CONFIG=/path/to/config.yaml ./gui/run_gui.sh
```

phone location bridge の OSRM ルートに `guidance_steps` がある場合、GUI は既定で Irodori backend に次の案内を渡し、生成された音声を再生します。案内ステップが進んだ時と、次の交差点などの約 1 km 手前、約 300 m 手前で読み上げます。

```bash
ENABLE_ROUTE_VOICE_GUIDANCE=0 ./gui/run_gui.sh
ROUTE_VOICE_EARLY_PREANNOUNCE_DISTANCE_M=800 ./gui/run_gui.sh
ROUTE_VOICE_PREANNOUNCE_DISTANCE_M=200 ./gui/run_gui.sh
```

GUI 右側の `Camera`、`Scan`、`Lane`、`Objects`、`Speed`、`Mode`、`GPS`、`Shadow` ボタンで、表示データを項目ごとに Demo / ROS2 へ切り替えできます。各ボタンは、対応する ROS2 トピックのメッセージを実際に受信するまで無効です。

起動時点から ROS2 優先にしたい場合は、以下のように指定します。トピックが届くまでは Demo 表示で起動し、受信できた項目から ROS2 表示に切り替わります。

```bash
uv run main.py --data-source ros2
```

ダークモードは既定で有効です。GUI左上の `Dark` チェック、または起動引数で切り替えできます。

```bash
uv run main.py --theme light
uv run main.py --theme dark
```

ROS2 モードでは、実行環境に `rclpy`、`sensor_msgs`、`std_msgs`、`numpy` が入っている必要があります。

使用するトピック名も引数で上書きできます。

```bash
uv run main.py \
  --data-source ros2 \
  --ros-camera-image-topic /sensing/camera/camera0/image_rect_color \
  --ros-camera-info-topic /sensing/camera/camera0/camera_info \
  --ros-scan-topic /scan_surroundings \
  --ros-lane-topic /scan \
  --ros-objects-topic /detected_objects \
  --ros-speed-topic /vehicle/speed_kmh \
  --ros-mode-topic /vehicle/mode \
  --ros-gps-topic /vehicle/gps_status \
  --ros-shadow-summary-topic /shadow/metrics/summary
```

`--ros-objects-topic` は `std_msgs/String` で、JSON 配列を想定しています。各要素は以下の形式です。

```json
[
  {"x_m": 1.2, "y_m": 5.6, "kind": "obstacle"},
  {"x_m": -2.4, "y_m": 9.1, "kind": "obstacle"}
]
```

そのほかの想定メッセージ型:

- `--ros-camera-image-topic`: `sensor_msgs/msg/Image`
- `--ros-camera-overlay-topic`: `sensor_msgs/msg/Image`。既定の `/shadow/e2e/overlay_image` が流れている間は通常カメラ画像より優先して Camera view に表示します。
- `--ros-camera-compressed-overlay-topic`: `sensor_msgs/msg/CompressedImage`。既定の `/shadow/e2e/overlay_image/compressed` を Camera view に優先表示します。
- `--ros-camera-overlay-timeout-sec`: overlay 画像が途切れてから通常カメラ画像へ戻すまでの秒数
- `--no-ros-camera-raw-overlay-fallback`: compressed overlay だけを Camera view に使い、raw overlay image の購読を無効化します。E2E launcher 経由の `run_gui.sh` では既定で有効です。
- `--no-ros-camera-raw-fallback`: overlay だけを Camera view に使い、raw camera image の購読を無効化します。E2E launcher 経由の `run_gui.sh` では既定で有効です。
- `--ros-camera-display-max-edge-px`: Camera view に渡す前に画像の長辺をこの値へ縮小します。`0` で縮小を無効化します。
- `--ros-camera-info-topic`: `sensor_msgs/msg/CameraInfo`
- `--ros-pointcloud-topic`: `sensor_msgs/msg/PointCloud2`。既定は FAST-LIO の `/cloud_registered` です。
- `--ros-pointcloud-odom-topic`: `nav_msgs/msg/Odometry`。既定は FAST-LIO の `/Odometry` です。PointCloud view はこのposeで `/cloud_registered` を現在車両基準へ戻して、点群が走行位置に合わせて表示範囲外へ流れないようにします。
- `--no-ros-pointcloud-stabilize-with-odom`: PointCloud view の odometry 補正を無効化し、PointCloud2 の座標をそのまま描画します。
- `--ros-pointcloud-max-points`: PointCloud view に渡す最大点数。既定は `2500` です。
- `--ros-pointcloud-min-update-interval-sec`: PointCloud view 表示中に別 worker で点群を parse する最短更新間隔。既定は `0.2` 秒です。
- `--ros-pointcloud-max-range-m`: PointCloud view に渡す最大水平距離。既定は `80.0` m です。3D view の表示レンジもこの値で固定します。
- `--ros-pointcloud-z-min-m` / `--ros-pointcloud-z-max-m`: PointCloud view に渡す高さ範囲。既定は `-3.0` m から `3.0` m です。
- `--ros-route-pointcloud-topic`: PointCloud view に重ねる route publisher 由来の `sensor_msgs/msg/PointCloud2`。既定は `/shadow/route/pointcloud` です。
- `--ros-route-pointcloud-max-points`: route pointcloud overlay に渡す最大点数。既定は `1500` です。
- `--ros-route-path-topic`: PointCloud view に重ねる route path `nav_msgs/msg/Path`。既定は `/shadow/route/gui_path` です。
- `--ros-e2e-path-topic`: PointCloud view に重ねる TransFuser 予測経路 `nav_msgs/msg/Path`。既定は `/shadow/e2e/path` です。
- `--ros-scan-topic`: `sensor_msgs/msg/LaserScan`
- `--ros-lane-topic`: `sensor_msgs/msg/LaserScan`
- `--ros-speed-topic`: `std_msgs/msg/Float32`
- `--ros-mode-topic`: `std_msgs/msg/String`
- `--ros-gps-topic`: `std_msgs/msg/String`
- `--tts-backend-url`: Irodori-TTS-Lite backend URL。既定は `http://127.0.0.1:8766` です。
- `--disable-route-voice-guidance`: OSRM / phone route guidance の音声案内を無効化します。
- `--route-voice-early-preannounce-distance-m`: 次の案内地点に近づいた時の早めの事前読み上げ距離。既定は `1000.0` m です。
- `--route-voice-preannounce-distance-m`: 次の案内地点に近づいた時の事前読み上げ距離。既定は `300.0` m です。
- `--gpu-monitor-interval-sec`: `nvidia-smi` でGPU使用率を読む周期。既定は `1.0` 秒です。
- `--disable-gpu-monitor`: GPU監視を無効化します。`nvidia-smi` が使えない環境でもGUI起動自体は継続します。
- `--rosbag-record-dir`: GUIの `ROS bag` パネルから録画したbagを保存するディレクトリ。既定は `Data/gui_rosbags` です。
- `--ros-e2e-pointcloud-topic`: E2E LiDAR raster 用の `PointCloud2`。既定は `/cloud_registered_body` です。
- `--ros-e2e-model-input-image-topic`: E2E model に渡す前処理済み画像。既定は `/shadow/e2e/model_input_image` です。
- `--ros-e2e-status-topic`: E2E runtime status。既定は `/shadow/e2e/status` です。
- `--ros-e2e-raw-lead-path-topic`: LEAD 座標解釈前の raw path。既定は `/shadow/e2e/path_raw_lead` です。
- `--ros-route-target-topic`: route target point。既定は `/shadow/route/target_point` です。
- `--ros-route-target-path-topic`: route target source から選択された Path。既定は `/shadow/route/target_path` です。
- `--rosbag-record-topic`: 既定の点群、カメラ、Odometry/GPS、route target、E2E診断、TFに加えて録画するtopic。複数指定できます。
- `--rosbag-record-preset`: 起動時に選択する録画プリセット。既定は `E2E input` です。

GUIの `ROS bag` パネルでは、録画プリセットを選んでから `録画` で `ros2 bag record` を開始し、`録画停止` でSIGINT停止してmetadataを書き出します。`E2E input` はShadowMode E2E replay向けの入力topicに加えて `/cloud_registered_body`、`/shadow/e2e/model_input_image`、`/shadow/e2e/status`、`/shadow/e2e/path_raw_lead`、`/shadow/route/target_point`、`/shadow/route/target_path`、TFを記録します。`GUI replay` はGUI表示確認向けにoverlayやshadow出力も含めます。`再生` は最後に録画したbag、または `選択` で指定したbagディレクトリを `ros2 bag play` します。`gui/run_gui.sh` からは保存先、起動時プリセット、追加topicを環境変数で上書きできます。

```bash
ROSBAG_RECORD_DIR=/path/to/bags ./gui/run_gui.sh
ROSBAG_RECORD_PRESET="GUI replay" ./gui/run_gui.sh
ROSBAG_RECORD_EXTRA_TOPICS="/vehicle/twist /diagnostics" ./gui/run_gui.sh
```

shadow-mode 欄は以下の `std_msgs/msg/Float32` と `std_msgs/msg/String` を既定で購読します。

- `/shadow/ego/speed`
- `/shadow/ego/yaw_rate`
- `/shadow/ego/curvature`
- `/shadow/virtual/steering_proxy`
- `/shadow/virtual/curvature`
- `/shadow/virtual/warning_score`
- `/shadow/metrics/driver_steering_proxy`
- `/shadow/metrics/steering_delta`
- `/shadow/metrics/curvature_delta`
- `/shadow/metrics/intervention_score`
- `/shadow/metrics/summary`

`gui/run_gui.sh` から起動する場合は、`GUI_THEME=light ./gui/run_gui.sh`、`ROS_CAMERA_IMAGE_TOPIC=/foo ROS_CAMERA_COMPRESSED_OVERLAY_TOPIC=/bar ROS_CAMERA_DISPLAY_MAX_EDGE_PX=960 ROS_CAMERA_INFO_TOPIC=/bar ./gui/run_gui.sh`、`ROS_CAMERA_RAW_OVERLAY_FALLBACK=1 ./gui/run_gui.sh`、`ROS_POINTCLOUD_TOPIC=/cloud_registered ROS_POINTCLOUD_ODOM_TOPIC=/Odometry ROS_POINTCLOUD_MAX_POINTS=1800 ROS_POINTCLOUD_MIN_UPDATE_INTERVAL_SEC=0.25 ROS_POINTCLOUD_MAX_RANGE_M=60 ./gui/run_gui.sh`、`ROS_ROUTE_POINTCLOUD_TOPIC=/shadow/route/pointcloud ROS_ROUTE_PATH_TOPIC=/shadow/route/gui_path ROS_E2E_PATH_TOPIC=/shadow/e2e/path ./gui/run_gui.sh`、`ROS_POINTCLOUD_STABILIZE_WITH_ODOM=0 ./gui/run_gui.sh`、`ROUTE_VOICE_PREANNOUNCE_DISTANCE_M=200 ./gui/run_gui.sh`、`ENABLE_ROUTE_VOICE_GUIDANCE=0 ./gui/run_gui.sh`、`ROS_SHADOW_INTERVENTION_SCORE_TOPIC=/foo ./gui/run_gui.sh` のように環境変数で上書きできます。

GUI の見た目は `gui/config/ui.yaml` で調整できます。必要なら `--ui-config` で別ファイルも指定できます。

```bash
uv run main.py --ui-config /path/to/ui.yaml
```

表示レンジを速度に応じて変えたい場合は、`gui/config/ui.yaml` の以下を調整してください。

```yaml
render:
  dynamic_range_enabled: true
  dynamic_range_min_m: 12.0
  dynamic_range_max_m: 35.0
  dynamic_range_speed_min_kmh: 0.0
  dynamic_range_speed_max_kmh: 80.0
```

## 地図の操作

- **ドラッグ**: 地図を移動
- **スクロール**: ズームイン/アウト
- **検索ボックス**: 地名や住所で場所を検索
  - 出発地と目的地を入力
  - 「ルート検索」ボタンクリックまたはEnterキー
- **ルート情報**: 右上に距離・時間が表示

## ルート検索機能

**OpenRouteService** と **Leaflet Control Geocoder** を使用した検索ベースのルート検索機能を実装しています。

### 特徴:
- ✅ **完全に無料** - APIキー不要
- ✅ **場所検索** - 地名・住所で検索可能
- ✅ **複数経路**: 車/徒歩/自転車に対応
- ✅ **リアルタイム計算** - 道路状況を考慮
- ✅ **日本語対応** - 距離と時間を日本語で表示

### 使用方法:
1. **出発地**を検索ボックスに入力（例: 東京駅）
2. **目的地**を検索ボックスに入力（例: 渋谷駅）
3. **「ルート検索」ボタン**をクリックまたはEnterキー
4. 自動的にルートが計算・表示されます
5. 右上に**ルート情報**（距離・時間）が表示されます

### 検索例:
- 駅名: 「東京駅」「渋谷駅」「新宿駅」
- 地名: 「東京タワー」「渋谷」「原宿」
- ランドマーク: 「東京スカイツリー」「ディズニーランド」
- 住所: 「東京都港区赤坂1-1-1」 ※一部の住所のみ対応

### 住所検索の制限:
**OpenStreetMapのNominatim APIを使用しているため、住所検索には以下の制限があります:**
- ✅ 駅名・ランドマーク・地名: 比較的検索しやすい
- ⚠️ 詳細な住所: 「東京都港区赤坂1-1-1」のような具体的な住所は検索できない場合が多い
- ✅ 市区町村レベル: 「渋谷区」「港区」などの広い範囲は検索可能
- ✅ 建物名: 「東京駅」「渋谷駅」などの有名施設は検索可能

**住所が検索できない場合の対処法:**
1. 駅名やランドマーク名で検索（例: 「東京駅」→「東京駅」）
2. 市区町村名で検索（例: 「渋谷区」）
3. 建物名や施設名で検索（例: 「東京タワー」）

これはOpenStreetMapのデータ制約によるもので、Google Mapsなどの商用サービスではより詳細な住所検索が可能です。

### ルート検索サービスの比較:

| サービス | 料金 | APIキー | 特徴 |
|----------|------|---------|------|
| **OpenRouteService** | 無料 | 不要 | ヨーロッパ中心、世界対応 |
| GraphHopper | 無料枠あり | 必要 | 高精度、世界対応 |
| Mapbox Directions | 無料枠あり | 必要 | 高精度、リアルタイム交通情報 |
| HERE Routing | 無料枠あり | 必要 | 高精度、リアルタイム交通情報 |
| Google Directions | 有料 | 必要 | 最高精度、ストリートビュー連携 |

## 日本語フォント

Linux環境では、日本語表示のために以下のフォントが自動的にインストールされます：
- Noto Sans CJK JP
- IPAGothic
- TakaoGothic

## 代替案

より高度な地図機能が必要な場合は、以下のサービスも検討してください：

1. **Mapbox** - 無料枠あり、衛星写真・ストリートビュー相当の機能
2. **HERE Maps** - 無料枠あり、高精度な地図データ
3. **Bing Maps** - Microsoft提供、無料枠あり

ただし、これらはAPIキーが必要で、使用量に応じた料金が発生する可能性があります。

## 日本語入力のトラブルシューティング

アプリケーションの検索ボックスで日本語入力ができない場合、以下の手順を試してください：

### IME設定の確認
1. **推奨**:
   ルートの `setup/ubuntu_setup.sh` を実行してください。WSL の場合は `.bashrc` 経由で `ubuntu_env.sh` が読み込まれ、`ibus-daemon` の起動と `mozc-jp` の選択まで自動化されます。

2. **手動で設定する場合**:
   ```bash
   sudo apt update
   sudo apt install ibus ibus-mozc dbus-x11 im-config
   im-config -n ibus
   export QT_IM_MODULE=ibus
   export XMODIFIERS=@im=ibus
   export GTK_IM_MODULE=ibus
   ```

3. **IBusの再起動**:
   ```bash
   ibus restart
   ```

### 代替IME
IBusが動作しない場合、fcitxを使用してください：
```bash
sudo apt install fcitx-mozc
im-config -n fcitx
export QT_IM_MODULE=fcitx
export XMODIFIERS=@im=fcitx
export GTK_IM_MODULE=fcitx
fcitx-autostart
```

### キーボード入力モードの切り替え
アプリケーション起動後に、以下の手順で日本語入力モードに切り替えてください：

1. **検索ボックスをクリック**してフォーカスを合わせる
2. **IME切り替えキー**を使用：
   - `半角/全角キー` (通常はスペースキーの左隣)
   - `Ctrl + スペース` (IBusの場合)
   - `Super + スペース` (一部の環境)

3. **入力モードの確認**：
   - 日本語入力モード：ローマ字入力が可能
   - 英語入力モード：直接英語入力

### 追加のIME設定
```bash
# IBusの詳細設定
ibus-setup

# キーボードショートカットの確認
gsettings get org.gnome.desktop.input-sources xkb-options
```

### 既知の問題と回避策
- **切り替えが効かない場合**：一度ウィンドウをクリックしてフォーカスを移動してから再試行
- **入力が遅い場合**：不要なIME拡張機能を無効化
- **Wayland環境**：X11環境への切り替えを検討
