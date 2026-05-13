# Shadow-mode 全体仕様書

作成日: 2026-04-23

## 1. 目的

AMaRanthus の `shadow_mode` は、実車または録画データから得られるセンサ・自己位置推定情報を使い、車両を直接制御せずに仮想的な走行判断を生成・可視化・記録するための ADAS 評価基盤である。

このシステムは自動運転の実車制御スタックではなく、以下を目的とした shadow-mode 評価プラットフォームとして扱う。

- 実車制御に介入せず、仮想ステアリングや警告スコアを生成する
- Ego motion と仮想制御出力を `/shadow/...` 配下の ROS 2 トピックに整理する
- Livox / FAST-LIO / lane detection など既存ワークスペース資産を接続する
- rosbag replay とログ記録で、同じシナリオを再現評価できる形にする
- 将来的に driver-vs-virtual 比較、メトリクス、GUI/HMI へ拡張できる構造にする

## 2. 非目標

現段階の `shadow_mode` では以下を行わない。

- アクセル、ブレーキ、ステアリングなどの実アクチュエータ制御
- 公道での自律走行
- Autoware / Nav2 によるフルスタック自動運転
- 完全な HD map 前提の経路計画
- 法規適合や量産 ADAS 相当の安全保証

## 3. 現在の構成

### 3.1 パッケージ

| パッケージ | 役割 |
| --- | --- |
| `shadow_mode_bringup` | shadow-mode 評価パイプライン全体の起動入口 |
| `shadow_mode_ego_estimation` | FAST-LIO などの odometry から ego speed / yaw rate / curvature / path を推定 |
| `shadow_mode_virtual_control` | lane-oriented `LaserScan` または 3D `PointCloud2` から仮想中心線と仮想ステアリングを生成 |
| `shadow_mode_metrics` | Ego 曲率由来の driver proxy と仮想制御を同一 timestamp 軸で比較 |
| `adas_bringup` | Livox driver、Livox lane detection、pointcloud_to_laserscan の前段起動 |
| `livox_lane_detection` | Livox 点群から lane scan、色付き点群、障害物 JSON を生成 |
| `fast_lio` | 3D LiDAR-IMU odometry を `/Odometry` として供給する主軸候補 |

### 3.2 推奨データフロー

```text
Livox HAP 2D scan mode
  -> /livox/lidar
  -> livox_lane_detection_live_node
  -> /livox/lane_detection/scan
  -> shadow_virtual_control
  -> /shadow/virtual/path
  -> /shadow/virtual/steering_proxy
  -> /shadow/virtual/curvature
  -> /shadow/virtual/warning_score

Livox HAP 3D pointcloud mode
  -> /livox/lidar
  -> shadow_virtual_control(input_mode=pointcloud)
  -> /shadow/virtual/path
  -> /shadow/virtual/steering_proxy
  -> /shadow/virtual/curvature
  -> /shadow/virtual/warning_score

Livox HAP + IMU odometry mainline
  -> fast_lio
  -> /Odometry
  -> shadow_ego_estimation
  -> /shadow/ego/path
  -> /shadow/ego/speed
  -> /shadow/ego/yaw_rate
  -> /shadow/ego/curvature

/shadow/ego/* + /shadow/virtual/*
  -> shadow_mode_metrics
  -> /shadow/metrics/control_delta
  -> /shadow/metrics/summary
```

`pointcloud_to_laserscan` が生成する `/scan` は汎用 2D scan として残す。shadow-mode の仮想制御は既定では lane detection 由来の `/livox/lane_detection/scan` を使うが、`virtual_input_mode:=pointcloud` に切り替えることで Livox の 3D `PointCloud2` を直接使う実験モードにできる。

FAST-LIO を使う場合、3D LiDAR-IMU odometry は Ego 推定の主軸として扱う。メモリと計算資源が許す限り、`/Odometry` と 3D 点群を同時に記録して replay 評価できる構成を推奨する。

## 4. Bringup 仕様

### 4.1 起動パッケージ

`shadow_mode_bringup` は `ament_cmake` の bringup 専用パッケージで、以下をまとめて起動する。

- `adas_bringup` による Livox / lane detection 前段
- `shadow_mode_ego_estimation`
- `shadow_mode_virtual_control`
- `shadow_mode_metrics`
- 任意の shadow-mode 評価用 rosbag2 記録

### 4.2 起動コマンド

ライブセンサ前段も含める場合:

```bash
ros2 launch shadow_mode_bringup shadow_mode_bringup.launch.py
```

rosbag replay など、既に入力トピックが存在する場合:

```bash
ros2 launch shadow_mode_bringup shadow_mode_bringup.launch.py use_adas_bringup:=false
```

評価用 bag も同時に記録する場合:

```bash
ros2 launch shadow_mode_bringup shadow_mode_bringup.launch.py record_shadow_bag:=true
```

3D 点群を仮想制御入力にする場合:

```bash
ros2 launch shadow_mode_bringup shadow_mode_bringup.launch.py use_adas_bringup:=false virtual_input_mode:=pointcloud virtual_pointcloud_topic:=/livox/lidar
```

この場合は、別プロセスで Livox driver / FAST-LIO などが `/livox/lidar` と `/Odometry` を publish している前提とする。lane detection を同時に動かさないため、メモリ使用量を抑えやすい。

### 4.3 主な launch 引数

| 引数 | 既定値 | 意味 |
| --- | --- | --- |
| `use_adas_bringup` | `true` | Livox / ADAS 前段も起動する |
| `use_livox_rviz` | `false` | ADAS 前段起動時に Livox RViz launch を使う |
| `use_ego_estimation` | `true` | Ego 推定ノードを起動する |
| `use_virtual_control` | `true` | 仮想制御ノードを起動する |
| `use_metrics` | `true` | Ego と仮想制御の比較ノードを起動する |
| `pointcloud_topic` | `/livox/lidar` | Livox 点群入力 |
| `scan_topic` | `/scan` | 汎用 pointcloud_to_laserscan 出力 |
| `virtual_input_mode` | `scan` | 仮想制御入力。`scan` または `pointcloud` |
| `virtual_pointcloud_topic` | `/livox/lidar` | 3D `PointCloud2` 入力モードで使う topic |
| `pointcloud_z_min` | `-1.5` | 3D 点群入力で使う最小 z `[m]` |
| `pointcloud_z_max` | `1.5` | 3D 点群入力で使う最大 z `[m]` |
| `pointcloud_stride` | `1` | 3D 点群入力時の点間引き。`1` は全点処理 |
| `odom_topic` | `/Odometry` | Ego 推定の odometry 入力 |
| `lane_detection_scan_topic` | `/livox/lane_detection/scan` | 仮想制御の lane scan 入力 |
| `ego_output_frame` | `""` | Ego 出力 frame。空なら入力 frame を維持 |
| `virtual_output_frame` | `""` | 仮想経路 frame。空なら入力 scan frame を維持 |
| `record_shadow_bag` | `false` | 評価用 rosbag2 記録を有効化 |
| `metrics_csv_logging` | `false` | `shadow_mode_metrics` の CSV 出力を有効化 |
| `metrics_csv_path` | `Data/metrics/shadow_mode_metrics.csv` | CSV 出力先 |
| `bag_output` | `Data/rosbag/shadow_mode_bag` | rosbag2 保存先 |
| `bag_record_regex` | `(/shadow/.*\|/livox/lane_detection/.*\|/Odometry\|/path\|/scan)` | 記録対象 topic regex |

## 5. ノード仕様

### 5.1 `shadow_ego_estimation`

目的:

- `/Odometry` を受け取り、shadow-mode 評価用の ego state を publish する
- 過去 odometry をリングバッファ的に保持し、実走行軌跡を `Path` として可視化する

入力:

| Topic | 型 | 説明 |
| --- | --- | --- |
| `/Odometry` | `nav_msgs/msg/Odometry` | FAST-LIO などからの自己位置推定 |

出力:

| Topic | 型 | 説明 |
| --- | --- | --- |
| `/shadow/ego/path` | `nav_msgs/msg/Path` | Ego の過去軌跡 |
| `/shadow/ego/speed` | `std_msgs/msg/Float32` | 推定速度 `[m/s]` |
| `/shadow/ego/yaw_rate` | `std_msgs/msg/Float32` | 推定ヨーレート `[rad/s]` |
| `/shadow/ego/curvature` | `std_msgs/msg/Float32` | 推定曲率 `[1/m]` |
| `/shadow/ego/debug_markers` | `visualization_msgs/msg/MarkerArray` | RViz 用デバッグ軌跡 |

処理:

- odometry の位置差分と timestamp から速度を計算する
- quaternion から yaw を取り出し、yaw 差分から yaw rate を計算する
- speed / yaw rate は一次平滑化する
- 速度が `min_speed_for_curvature` 以上のときだけ `yaw_rate / speed` で曲率を計算する
- `path_buffer_size` 件分の pose を保持して `/shadow/ego/path` に publish する

主要パラメータ:

| パラメータ | 既定値 | 意味 |
| --- | --- | --- |
| `input_odom_topic` | `/Odometry` | 入力 odometry topic |
| `path_buffer_size` | `200` | 軌跡保持サンプル数 |
| `min_dt` | `0.01` | 推定に使う最小サンプル間隔 `[s]` |
| `min_speed_for_curvature` | `0.5` | 曲率計算を有効化する最低速度 `[m/s]` |
| `speed_smoothing_gain` | `0.2` | 速度平滑化ゲイン |
| `yaw_rate_smoothing_gain` | `0.2` | yaw rate 平滑化ゲイン |

### 5.2 `shadow_virtual_control`

目的:

- lane-oriented `LaserScan` または 3D `PointCloud2` から車線中心線の近似 path を作る
- Pure Pursuit により仮想ステアリング代理値を生成する
- 境界欠損と曲率代理値から簡易 warning score を出す

入力:

| Topic | 型 | 説明 |
| --- | --- | --- |
| `/livox/lane_detection/scan` | `sensor_msgs/msg/LaserScan` | `input_mode=scan` 時の lane detection 由来の境界/車線 scan |
| `/livox/lidar` | `sensor_msgs/msg/PointCloud2` | `input_mode=pointcloud` 時の 3D LiDAR 点群 |

出力:

| Topic | 型 | 説明 |
| --- | --- | --- |
| `/shadow/virtual/path` | `nav_msgs/msg/Path` | 推定中心線 path |
| `/shadow/virtual/steering_proxy` | `std_msgs/msg/Float32` | 仮想ステアリング角 `[rad]` |
| `/shadow/virtual/curvature` | `std_msgs/msg/Float32` | 仮想経路曲率 `[1/m]` |
| `/shadow/virtual/warning_score` | `std_msgs/msg/Float32` | `0.0` から `1.0` の警告スコア |
| `/shadow/virtual/debug_markers` | `visualization_msgs/msg/MarkerArray` | RViz 用中心線マーカー |

`input_mode=scan` の処理:

- `LaserScan` を極座標から前方 x-y 座標へ変換する
- 前方距離を `bin_size` ごとに区切り、左右境界点を分離する
- 左右境界が両方ある場合は中央値の中間を中心線とする
- 片側境界だけの場合は `assumed_lane_half_width` で中心線を補完する
- 中心線 path から lookahead target を選び、Pure Pursuit で曲率と仮想舵角を計算する
- 境界欠損率と path 曲率代理値を合成して warning score を計算する

`input_mode=pointcloud` の処理:

- 3D `PointCloud2` の x/y/z フィールドを読み取る
- `pointcloud_z_min` から `pointcloud_z_max` の点だけを使う
- `pointcloud_stride` により点を間引き、メモリと計算負荷を調整する
- 残った点を x-y 平面へ投影し、scan mode と同じビン分割・中心線生成・Pure Pursuit へ流す

3D pointcloud mode は raw 点群からの地面投影であり、lane detection ほど意味的に安定した入力ではない。FAST-LIO の 3D LiDAR odometry を主軸にしながら、メモリが許す場合に 3D 点群も記録・評価するための実験モードとして扱う。

主要パラメータ:

| パラメータ | 既定値 | 意味 |
| --- | --- | --- |
| `input_mode` | `scan` | `scan` または `pointcloud` |
| `input_scan_topic` | `/livox/lane_detection/scan` | 入力 lane scan topic |
| `input_pointcloud_topic` | `/livox/lidar` | 入力 3D pointcloud topic |
| `wheelbase` | `2.7` | Pure Pursuit のホイールベース `[m]` |
| `lookahead_distance` | `6.0` | 先読み距離 `[m]` |
| `max_steering_rad` | `0.6` | 仮想最大舵角 `[rad]` |
| `forward_min_distance` | `2.0` | 中心線生成の最小前方距離 `[m]` |
| `forward_max_distance` | `20.0` | 中心線生成の最大前方距離 `[m]` |
| `bin_size` | `1.0` | 前方ビン幅 `[m]` |
| `max_lateral_distance` | `8.0` | 横方向フィルタ範囲 `[m]` |
| `assumed_lane_half_width` | `1.75` | 片側境界欠損時に仮定する半車線幅 `[m]` |
| `min_points_per_side` | `1` | 境界ありとみなす最小点数 |
| `warning_missing_boundary_weight` | `0.7` | warning score の境界欠損重み |
| `warning_curvature_weight` | `0.3` | warning score の曲率重み |
| `pointcloud_z_min` | `-1.5` | 3D 点群入力で使う最小 z `[m]` |
| `pointcloud_z_max` | `1.5` | 3D 点群入力で使う最大 z `[m]` |
| `pointcloud_stride` | `1` | 3D 点群入力時の点間引き。`1` は全点処理 |

### 5.3 `shadow_mode_metrics`

目的:

- `/shadow/ego/*` と `/shadow/virtual/*` を同じ ROS 時刻軸で比較する
- 実ドライバ入力が未接続でも、Ego 曲率から driver steering proxy を推定して最小比較を成立させる
- 操舵差分、曲率差分、簡易 intervention score、JSON summary、任意 CSV を出力する

入力:

| Topic | 型 | 説明 |
| --- | --- | --- |
| `/shadow/ego/speed` | `std_msgs/msg/Float32` | Ego 推定速度 `[m/s]` |
| `/shadow/ego/curvature` | `std_msgs/msg/Float32` | Ego 推定曲率 `[1/m]` |
| `/shadow/virtual/steering_proxy` | `std_msgs/msg/Float32` | 仮想ステアリング `[rad]` |
| `/shadow/virtual/curvature` | `std_msgs/msg/Float32` | 仮想経路曲率 `[1/m]` |
| `/shadow/virtual/warning_score` | `std_msgs/msg/Float32` | 仮想制御側 warning score |

出力:

| Topic | 型 | 説明 |
| --- | --- | --- |
| `/shadow/metrics/driver_steering_proxy` | `std_msgs/msg/Float32` | Ego 曲率から推定した driver steering proxy `[rad]` |
| `/shadow/metrics/steering_delta` | `std_msgs/msg/Float32` | `virtual_steering - driver_steering_proxy` `[rad]` |
| `/shadow/metrics/curvature_delta` | `std_msgs/msg/Float32` | `virtual_curvature - ego_curvature` `[1/m]` |
| `/shadow/metrics/intervention_score` | `std_msgs/msg/Float32` | 操舵差分、曲率差分、warning を合成した `0.0` から `1.0` の評価値 |
| `/shadow/metrics/control_delta` | `geometry_msgs/msg/Vector3Stamped` | stamped metric。`x=steering_delta`, `y=curvature_delta`, `z=intervention_score` |
| `/shadow/metrics/summary` | `std_msgs/msg/String` | JSON summary |

処理:

- 各 `Float32` 入力を受信時刻付きでキャッシュする
- `max_signal_age_sec` 以内に揃った最新サンプルだけを比較対象にする
- `driver_steering_proxy = atan(wheelbase * ego_curvature)` を計算する
- 仮想ステアリングとの差分、仮想曲率との差分を計算する
- 閾値正規化した差分と warning score を重み付き合成し、`intervention_score` を算出する
- `enable_csv_logging=true` の場合、CSV に時系列メトリクスを追記する

主要パラメータ:

| パラメータ | 既定値 | 意味 |
| --- | --- | --- |
| `wheelbase` | `2.7` | driver steering proxy 変換に使うホイールベース `[m]` |
| `publish_rate_hz` | `10.0` | メトリクス publish 周期 |
| `max_signal_age_sec` | `0.5` | 同一時刻軸として許容する最新サンプル年齢 `[s]` |
| `steering_delta_warn_rad` | `0.2` | intervention score 正規化用の操舵差分閾値 `[rad]` |
| `curvature_delta_warn_inv_m` | `0.1` | intervention score 正規化用の曲率差分閾値 `[1/m]` |
| `steering_delta_weight` | `0.5` | intervention score の操舵差分重み |
| `curvature_delta_weight` | `0.3` | intervention score の曲率差分重み |
| `virtual_warning_weight` | `0.2` | intervention score の仮想 warning 重み |
| `enable_csv_logging` | `false` | CSV ログ保存の有効化 |
| `csv_path` | `Data/metrics/shadow_mode_metrics.csv` | CSV 出力先 |

## 6. 運用モード

### 6.1 Live Livox mode

Livox HAP 実機を使い、`adas_bringup` と shadow-mode ノードを同時起動する。既定では `virtual_input_mode=scan` により lane detection 由来の 2D scan を仮想制御へ入力する。3D 点群で評価したい場合は `virtual_input_mode:=pointcloud` に切り替える。

### 6.2 FAST-LIO 3D odometry mode

FAST-LIO の `/Odometry` を Ego 推定の主入力として使う運用モード。3D LiDAR-IMU odometry を shadow-mode の基準軌跡にし、`shadow_mode_metrics` が Ego 曲率由来の driver proxy と仮想制御を比較する。

推奨記録 topic:

- `/livox/lidar`
- `/livox/imu` または FAST-LIO が要求する IMU topic
- `/Odometry`
- `/path`
- `/shadow/ego/*`
- `/shadow/virtual/*`
- `/shadow/metrics/*`

### 6.3 Replay mode

rosbag2 から `/livox/lane_detection/scan`、`/livox/lidar`、`/Odometry` などを再生し、`use_adas_bringup:=false` で shadow-mode ノードだけを起動する。アルゴリズム調整、メトリクス比較、デモ動画作成に向く。

### 6.4 Module-only mode

`use_ego_estimation`、`use_virtual_control`、`use_metrics` を切り替えて必要なノードだけを起動する。FAST-LIO 側の調整、lane scan / pointcloud 側の調整、メトリクス個別デバッグに使う。

## 7. 安全仕様

- shadow-mode は `/shadow/...` 配下への publish を基本とする
- 車両制御用の `/control_cmd`、`/vehicle_cmd`、CAN 書き込み系 topic / service は publish しない
- `steering_proxy` は仮想評価値であり、実車 steering command ではない
- `driver_steering_proxy` は Ego 曲率から逆算した代理値であり、実ステアリング角ではない
- warning score は安全評価の代理指標であり、運転判断の最終責任を置くものではない
- 実機検証時は、まず bag replay と停止車両状態で topic / frame / timestamp を確認する

## 8. 評価・受け入れ基準

MVP として以下を満たせば、shadow-mode 基盤として成立とする。

- `colcon build --packages-select shadow_mode_bringup shadow_mode_ego_estimation shadow_mode_virtual_control shadow_mode_metrics` が成功する
- `ros2 launch shadow_mode_bringup shadow_mode_bringup.launch.py use_adas_bringup:=false` で shadow ノードが起動する
- `/Odometry` 入力に対して `/shadow/ego/path` と `/shadow/ego/speed` が publish される
- `/livox/lane_detection/scan` 入力に対して `/shadow/virtual/path` と `/shadow/virtual/steering_proxy` が publish される
- `virtual_input_mode:=pointcloud` のとき `/livox/lidar` 入力に対して `/shadow/virtual/path` と `/shadow/virtual/steering_proxy` が publish される
- `/shadow/ego/*` と `/shadow/virtual/*` 入力が揃ったとき `/shadow/metrics/control_delta` と `/shadow/metrics/summary` が publish される
- RViz で `/shadow/ego/debug_markers` と `/shadow/virtual/debug_markers` を確認できる
- `record_shadow_bag:=true` で評価用トピックを rosbag2 に保存できる

## 9. 既知の制限

- 現時点では実 driver 操作量との直接比較は未実装であり、`shadow_mode_metrics` は Ego 曲率由来の driver proxy を使う
- 実ステアリング角、ペダル操作、CAN/OBD 入力の adapter は未実装
- 仮想制御は Pure Pursuit ベースであり、障害物回避や速度計画はまだ含まない
- 3D pointcloud mode は raw 点群の x-y 投影であり、地物・障害物・ノイズを意味的に分離しない
- warning score は境界欠損と曲率 proxy の簡易合成であり、TTC や衝突リスクの完全評価ではない
- frame transform の厳密な整合は入力側の frame 設計に依存する

## 10. 今後の拡張

優先度の高い拡張候補:

- `shadow_mode_driver_input`: CAN/OBD/手動アノテーションから driver steering / accel / brake proxy を作る
- `shadow_mode_metrics` の driver input 対応: Ego 曲率由来 proxy ではなく実ステアリング角・ペダル操作を比較対象にする
- `shadow_mode_dashboard`: GUI または RViz panel で steering delta、warning score、path 差分を可視化する
- `shadow_mode_replay_tools`: bag replay、シナリオ名、結果ディレクトリを揃える実験スクリプト
- `shadow_mode_autoware_adapter`: Autoware/Navigation2 の trajectory / control reference と比較する adapter
- `e2e_transfuser`: `amaranthus/src/adas/e2e_transfuser` に配置し、LEAD / TransFuser V6 系モデルを shadow-mode の `/shadow/e2e/*` 出力として接続する。仕様は `doc/lead_transfuser_ros2_specification_ja.md` に分離する

次の推奨フェーズは、`shadow_mode_driver_input` を追加し、CAN/OBD または手動アノテーションから実 driver steering / accel / brake proxy を受け取れるようにすることである。その後、`shadow_mode_metrics` の比較対象を Ego 曲率由来 proxy から実 driver input へ切り替える。
