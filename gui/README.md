# Robot UI Sample

ロボット用のGUIサンプルアプリケーションです。

## 機能

- **地図表示**: OpenStreetMap + Leafletを使用（APIキー不要・無料）
- **ルート検索**: OpenRouteServiceを使用（APIキー不要・無料）
- ステータス表示（車速、前方最短距離、障害物数、モード、GPS）
- レーザースキャンデータの可視化
- lane / road edge のオーバーレイ表示
- 検知された obstacle マーカー表示

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

デモデータではなく ROS2 トピックを読みたい場合は、起動時に切り替えできます。

```bash
uv run main.py --data-source ros2
```

ROS2 モードでは、実行環境に `rclpy`、`sensor_msgs`、`std_msgs` が入っている必要があります。

使用するトピック名も引数で上書きできます。

```bash
uv run main.py \
  --data-source ros2 \
  --ros-scan-topic /scan_surroundings \
  --ros-lane-topic /scan \
  --ros-objects-topic /detected_objects \
  --ros-speed-topic /vehicle/speed_kmh \
  --ros-mode-topic /vehicle/mode \
  --ros-gps-topic /vehicle/gps_status
```

`--ros-objects-topic` は `std_msgs/String` で、JSON 配列を想定しています。各要素は以下の形式です。

```json
[
  {"x_m": 1.2, "y_m": 5.6, "kind": "obstacle"},
  {"x_m": -2.4, "y_m": 9.1, "kind": "obstacle"}
]
```

そのほかの想定メッセージ型:

- `--ros-scan-topic`: `sensor_msgs/msg/LaserScan`
- `--ros-lane-topic`: `sensor_msgs/msg/LaserScan`
- `--ros-speed-topic`: `std_msgs/msg/Float32`
- `--ros-mode-topic`: `std_msgs/msg/String`
- `--ros-gps-topic`: `std_msgs/msg/String`

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
