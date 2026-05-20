# shadow_mode_bringup

`shadow_mode_bringup` は、AMaRanthus ワークスペースの shadow-mode ADAS 評価パイプラインをまとめて起動するための bringup パッケージです。

このパッケージは実車のアクチュエータを制御しません。Livox/ADAS 前段、Ego 推定、仮想制御生成、メトリクス生成を接続し、`/shadow/...` 配下に評価・可視化用トピックを publish します。

## 起動例

Livox ADAS 前段も含めて起動します。

```bash
ros2 launch shadow_mode_bringup shadow_mode_bringup.launch.py
```

Autoware も同じ導線で起動し、センサ入力は AMaRanthus 側の Livox / odometry を使う場合:

```bash
ros2 launch shadow_mode_bringup shadow_mode_autoware_bringup.launch.py map_path:=/path/to/map
```

この launch は `shadow_mode_bringup.launch.py` を含めたうえで、`/livox/lidar` を Autoware の `/sensing/lidar/concatenated/pointcloud` と `/sensing/lidar/top/pointcloud_raw_ex` へ relay し、`/Odometry` を `/localization/kinematic_state` へ relay します。Autoware 側の `launch_sensing`、`launch_localization`、`launch_vehicle_interface` は false 固定です。

rosbag や既存トピックを replay する場合は、センサ前段を起動せず shadow-mode ノードだけを立ち上げます。

```bash
ros2 launch shadow_mode_bringup shadow_mode_bringup.launch.py use_adas_bringup:=false
```

この replay 構成では、Livox/ADAS 前段パッケージをビルドしていなくても `shadow_mode_ego_estimation`、`shadow_mode_virtual_control`、`shadow_mode_metrics` だけで起動できます。`/Odometry` から車速・曲率・操舵 proxy を推定し、実 CAN / OBD の driver input は使いません。

評価用 bag も同時に記録します。

```bash
ros2 launch shadow_mode_bringup shadow_mode_bringup.launch.py record_shadow_bag:=true
```

同じ replay 評価を繰り返す場合は、`shadow_mode_replay_tools` で bag 再生、CSV 出力、shadow bag 記録をまとめて実行できます。

```bash
ros2 run shadow_mode_replay_tools shadow_mode_replay.py --bag Data/rosbag/sample_drive --scenario sample_drive
```

3D 点群を仮想制御入力にする場合は、`virtual_input_mode:=pointcloud` を指定します。

```bash
ros2 launch shadow_mode_bringup shadow_mode_bringup.launch.py use_adas_bringup:=false virtual_input_mode:=pointcloud virtual_pointcloud_topic:=/livox/lidar
```

この場合は、別ターミナルで Livox driver / FAST-LIO などが `/livox/lidar` と `/Odometry` を publish している前提です。

## 主な入力

- `/livox/lidar`: Livox PointCloud2 入力
- `/livox/lane_detection/scan`: lane-oriented LaserScan 入力
- `/Odometry`: FAST-LIO などからの ego odometry 入力

## 主な出力

- `/shadow/ego/path`
- `/shadow/ego/speed`
- `/shadow/ego/yaw_rate`
- `/shadow/ego/curvature`
- `/shadow/virtual/path`
- `/shadow/virtual/steering_proxy`
- `/shadow/virtual/curvature`
- `/shadow/virtual/warning_score`
- `/shadow/metrics/driver_steering_proxy`
- `/shadow/metrics/steering_delta`
- `/shadow/metrics/curvature_delta`
- `/shadow/metrics/intervention_score`
- `/shadow/metrics/summary`
- `/shadow/ego/debug_markers`
- `/shadow/virtual/debug_markers`

## 主要 launch 引数

- `use_adas_bringup`: `adas_bringup` を含めて Livox/ADAS 前段を起動します。
- `use_ego_estimation`: Ego 推定ノードを起動します。
- `use_virtual_control`: 仮想制御ノードを起動します。
- `use_metrics`: Ego と仮想制御の比較メトリクスノードを起動します。
- `pointcloud_to_laserscan_param_file`: ADAS 前段用のパラメータファイルです。空なら `use_adas_bringup:=true` の時だけ既定値を解決します。
- `lane_detection_model_path`: lane detection モデルパスです。空なら `use_adas_bringup:=true` の時だけ既定値を解決します。
- `virtual_input_mode`: 仮想制御入力を `scan` または `pointcloud` から選びます。
- `virtual_pointcloud_topic`: 3D `PointCloud2` 入力モードで使うトピックです。
- `odom_topic`: Ego 推定に使う odometry トピックです。
- `lane_detection_scan_topic`: 仮想制御に使う LaserScan トピックです。
- `record_shadow_bag`: 評価用トピックを rosbag2 に記録します。
- `metrics_csv_logging`: メトリクス CSV ログを保存します。
