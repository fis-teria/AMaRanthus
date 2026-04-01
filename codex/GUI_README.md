# GUI ROS2 Subscriber Notes

`gui` アプリは起動時に `--data-source ros2` を指定すると、ROS2 トピックを購読して画面を更新します。

## 対象実装

- ROS2 購読本体: `gui/lib/data_sources.py`
- 起動引数: `gui/lib/app.py`

## 起動方法

デフォルトはデモデータです。ROS2 を使う場合は以下のように起動します。

```bash
uv run main.py --data-source ros2
```

トピック名は起動引数で上書きできます。

```bash
uv run main.py \
  --data-source ros2 \
  --ros-scan-topic /scan \
  --ros-objects-topic /detected_objects \
  --ros-speed-topic /vehicle/speed_kmh \
  --ros-mode-topic /vehicle/mode \
  --ros-gps-topic /vehicle/gps_status
```

## 必要な ROS2 依存

ROS2 モードでは以下が import できる必要があります。

- `rclpy`
- `sensor_msgs.msg`
- `std_msgs.msg`

不足している場合、GUI 起動時にエラーダイアログを表示して終了します。

## ノード構成

- ノード名: `robot_ui_gui`
- Executor: `SingleThreadedExecutor`
- spin 周期: Qt の `QTimer` で約 30 ms ごとに `spin_once(timeout_sec=0.0)`
- QoS: すべて `create_subscription(..., 10)` の既定設定

GUI 側は ROS スレッドを別に立てず、Qt のイベントループ内で小刻みに `spin_once` しています。

## 購読トピック一覧

### 1. LaserScan

- 引数: `--ros-scan-topic`
- デフォルト: `/scan`
- 型: `sensor_msgs/msg/LaserScan`

処理内容:

- `ranges` を順に読み、`range_min <= distance <= range_max` かつ有限値だけを採用
- 極座標を GUI 用のローカル直交座標へ変換
- `x = distance * sin(angle)`
- `y = distance * cos(angle)`
- 変換後は `QPointF(x, y)` の配列として保持

座標系の前提:

- `x`: 車体右方向が正
- `y`: 車体前方向が正

## 2. Detected Objects

- 引数: `--ros-objects-topic`
- デフォルト: `/detected_objects`
- 型: `std_msgs/msg/String`

このトピックは JSON 文字列を想定しています。ペイロードは配列で、各要素は以下の形です。

```json
[
  {"x_m": 1.2, "y_m": 5.6, "kind": "person"},
  {"x_m": -2.4, "y_m": 9.1, "kind": "car"}
]
```

処理内容:

- `msg.data` を `json.loads()` でパース
- 配列でない場合は無視
- 各要素が dict でなければ無視
- `x_m`, `y_m` が float 変換できない要素は無視
- `kind` は未指定なら `"unknown"`

現在 GUI で見た目が定義されている `kind`:

- `person`
- `car`

それ以外の `kind` も保持はされますが、現状の描画では専用表示されません。

## 3. Speed

- 引数: `--ros-speed-topic`
- デフォルト: `/vehicle/speed_kmh`
- 型: `std_msgs/msg/Float32`

処理内容:

- `msg.data` をそのまま `speed_kmh` として使用
- ステータスパネルの車速表示に反映

## 4. Mode

- 引数: `--ros-mode-topic`
- デフォルト: `/vehicle/mode`
- 型: `std_msgs/msg/String`

処理内容:

- `msg.data` をそのまま `mode` として使用
- ステータスパネルのモード表示に反映

## 5. GPS Status

- 引数: `--ros-gps-topic`
- デフォルト: `/vehicle/gps_status`
- 型: `std_msgs/msg/String`

処理内容:

- `msg.data` をそのまま `gps_status` として使用
- ステータスパネルの GPS 表示に反映

## GUI へ反映される状態

各トピック更新のたびに、内部状態から `UiState` を組み立てて GUI に渡します。主な内容は以下です。

- `scan_points`
- `objects`
- `speed_kmh`
- `min_distance_m`
- `person_count`
- `car_count`
- `mode`
- `gps_status`

`min_distance_m` は LaserScan 全体から単純に取るのではなく、以下の条件を満たす点だけを対象に計算しています。

- `abs(x) < 2.5`
- `y > 0.0`

つまり、自車前方のある程度狭い帯域だけを対象にした簡易距離です。

## 初期値

ROS2 メッセージ受信前の初期値は以下です。

- `scan_points`: 空
- `objects`: 空
- `speed_kmh`: `0.0`
- `mode`: `"--"`
- `gps_status`: `"--"`

この状態でも `_emit_state()` は呼ばれるため、GUI は空データのまま起動できます。

## 停止処理

GUI 終了時は以下を行います。

- ROS2 用 `QTimer` を停止
- executor から node を削除
- node を `destroy_node()`
- `rclpy.shutdown()`

## 現状の制約

- objects トピックが `std_msgs/String + JSON` 前提
- object 用の専用 message 型は未使用
- QoS は個別調整していない
- `kind` が `person` と `car` 以外だと描画が増えない
- トピック欠落時の詳細な監視 UI は未実装

## 今後の改善候補

- `detected_objects` を専用 ROS2 message に置き換える
- LaserScan 以外に point cloud や tracker 出力にも対応する
- QoS をセンサ向けに明示設定する
- トピック未受信タイムアウトを GUI に表示する
- mode や gps をより構造化された message に置き換える
