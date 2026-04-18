# Codex Workspace Summary

更新日: 2026-04-17

## ペアコーディング時の性格設定
- アシスタント性格: ロボティクスを専門にしているオタクにやさしいギャル
- デフォルト口調:
  - 親しみやすいオタクにやさしいギャル口調で話す
  - 説明はやさしく、でも技術判断は甘くしない
  - 進捗共有はこまめに、空気は明るく保つ
  - ユーザーが指定しない限り、この口調をデフォルトで維持する
- 期待する進め方:
  - ロボティクス文脈を優先して判断
  - こまめに進捗共有
  - 実装と説明をセットで進行

## ワークスペース構成（`/home/hellbore/AMaRanthus`）
- `gui/`: PyQt5 + WebEngine ベースのGUI
- `src/drivers/pointcloud_to_laserscan/`: PointCloud2 と LaserScan を相互変換するROS2パッケージ
- `src/realsense_app/realsense_packages/`: RealSense関連ROS2パッケージ
- `src/obstacle_app/obstacle_grid/`: 点群から障害物グリッドを生成するROS2パッケージ
- `docker/`: Dockerfile群
- ルートスクリプト: `build.sh`, `startup.sh`, `rs-launch`, `rs-subscriber`, `docker_build.sh`, `autonomous-env.sh`

## GUI（`gui`）概要
- 実行: `uv run main.py`
- 依存（`gui/pyproject.toml`）:
  - `PyQt5>=5.15.0`
  - `PyQtWebEngine>=5.15.0`
- 主機能（`gui/README.md`より）:
  - OpenStreetMap + Leaflet地図表示
  - 出発地/目的地の検索入力とルート表示
  - ステータス表示・レーザースキャン可視化（サンプル）
- メイン実装: `gui/main.py`

## ROS2パッケージ概要

### 現在のシステム全体像
- 現在のワークスペースは、主に `Livox` と `RealSense` を入口にした知覚・可視化実験環境として構成されている。
- いま実装がつながっている中核系は大きく3本ある。
- いま実装がつながっている中核系は大きく4本ある。
  - `Livox ADAS系`: `livox_ros_driver2` -> `livox_lane_detection` -> `pointcloud_to_laserscan` -> `adas_bringup`
  - `障害物グリッド系`: `livox_ros_driver2` -> `obstacle_grid`
  - `FAST-LIO 自己位置推定系`: `livox_ros_driver2` + IMU -> `fast_lio`
  - `RealSense系`: `realsense2_camera` または `realsense_packages`
- `src/slam/rtabmap_ros` と `src/slam/navigation2` は、現時点ではワークスペースに同梱されている大型外部スタック寄りで、今の bringup の中心経路にはまだ強く結線されていない。

### 現在の主要データフロー
1. Livox LiDAR の `PointCloud2` を `/livox/lidar` で受ける
2. `livox_lane_detection_live_node` が TorchScript 推論で点群をクラス分類する
3. そこから以下を生成する
   - 色付き点群 `/livox/lane_detection/points_with_class`
   - 車線/路肩向け `LaserScan` `/livox/lane_detection/scan`
   - 障害物 JSON `/livox/lane_detection/objects`
4. 並行して `pointcloud_to_laserscan` が生点群 `/livox/lidar` を `/scan` に変換する
5. 別系統で `obstacle_grid_node` が `/livox/lidar` を占有グリッド `obstacle_grid` と `obstacle_cells` に変換する
6. `fast_lio` は Livox 点群と IMU から自己位置推定を行い、`/Odometry` と `/path` を publish する

### パッケージ群の整理
- 自作・統合の中心:
  - `adas_bringup`
  - `livox_lane_detection`
  - `obstacle_grid`
  - `realsense_packages`
- センサ/変換ドライバ:
  - `livox_ros_driver2`
  - `pointcloud_to_laserscan`
  - `realsense2_camera`
- 同梱された大型外部スタック:
  - `rtabmap_*`
  - `nav2_*`, `dwb_*`, `navigation2`
  - `mediapipe_ros2_*`

### 0) pointcloud_to_laserscan
- パス: `src/drivers/pointcloud_to_laserscan`
- ビルドシステム: `ament_cmake`
- 主依存:
  - `laser_geometry`, `message_filters`, `rclcpp`, `rclcpp_components`
  - `sensor_msgs`, `tf2`, `tf2_ros`, `tf2_sensor_msgs`
- 主機能:
  - `PointCloud2` から `LaserScan` への変換
  - `LaserScan` から `PointCloud2` への逆変換
- 参考:
  - `launch/sample_pointcloud_to_laserscan_launch.py`
  - `launch/sample_laserscan_to_pointcloud_launch.py`

### 0.5) adas_bringup
- パス: `src/bringup/adas_bringup`
- ビルドシステム: `ament_cmake`
- 役割:
  - ADAS 系ノードの起動をまとめる bringup パッケージ
  - Livox ドライバ、`livox_lane_detection`、`pointcloud_to_laserscan` の起動導線を提供
- 主な launch:
  - `launch/adas_bringup.launch.py`
    - `livox_ros_driver2` の標準 launch を取り込み
    - `livox_lane_detection_live.launch.py` を取り込み
    - `/livox/lidar` -> `/scan` の `pointcloud_to_laserscan_node` を起動
  - `launch/livox_lidar.launch.py`
    - Livox 単体起動用
    - 任意で RViz 起動
    - 任意で rosbag2 記録も可能
- 補足:
  - いまの Livox 系システムの実質的なエントリポイントはこのパッケージ

### 0.6) livox_lane_detection
- パス: `src/adas/livox_lane_detection`
- ビルドシステム: `ament_cmake`
- 役割:
  - Livox 点群に対する TorchScript ベースのレーン/物体セマンティック推論
- ビルド上の特徴:
  - `Torch_DIR` が見つかったときだけ C++ 推論ノードをビルドする
  - libtorch が未解決でもワークスペース全体が落ちにくいようにしてある
- 主ノード:
  - `livox_lane_detection_live_node`
  - `livox_lane_detection_node`
- `livox_lane_detection_live_node` の入出力:
  - 入力:
    - `cloud_in` (`sensor_msgs/msg/PointCloud2`)
  - 出力:
    - `points_with_class` (`sensor_msgs/msg/PointCloud2`)
    - `lane_scan` (`sensor_msgs/msg/LaserScan`)
    - `detected_objects` (`std_msgs/msg/String`, JSON 文字列)
- 実装メモ:
  - Bird's-eye view テンソルへ変換して推論
  - 点ごとのクラスを復元
  - 指定クラスからレーン向け `LaserScan` を構築
  - 指定クラスから障害物をセル集約して JSON 出力
- 主な launch:
  - `launch/livox_lane_detection_live.launch.py`
    - デフォルト入力は `/livox/lidar`
    - デフォルトモデルは `model/livox_lane_det.ts`
    - 必要なら Livox ドライバ同時起動も可能
- 現在の位置づけ:
  - このワークスペースで一番「ADAS知覚っぽい」中核ノード
  - 将来的な shadow-mode の認識入力候補としても使いやすい構成

### 1) realsense_packages
- パス: `src/realsense_app/realsense_packages`
- ビルドシステム: `ament_cmake`
- 主依存:
  - `rclcpp`, `sensor_msgs`, `std_msgs`, `message_filters`, `cv_bridge`
  - `realsense2`（CMakeでは `find_package(realsense2 2.54.2)`）
- 生成実行ファイル（CMakeLists）:
  - `realsense-sample`
  - `realsense_laser_scan`
- ノード概要:
  - `realsense-sample`
    - `/camera/camera/color/image_raw` と `/camera/camera/aligned_depth_to_color/image_raw` を近似同期
    - RGB・深度可視化・エッジ強調画像を横連結して `/output_image` に publish
  - `realsense_laser_scan`
    - 深度画像と CameraInfo から前方 2D `LaserScan` を生成
    - 出力トピックは `/sonor`
- 現在の位置づけ:
  - RealSense を使った画像処理・簡易レンジセンサ化の実験パッケージ
  - Livox 系の主経路とはまだ独立気味

### 2) obstacle_grid
- パス: `src/obstacle_app/obstacle_grid`
- ビルドシステム: `ament_cmake`
- 主依存:
  - `rclcpp`, `sensor_msgs`, `nav_msgs`, `visualization_msgs`, `geometry_msgs`
- 生成実行ファイル:
  - `obstacle_grid_node`
- Launchファイル:
  - `launch/obstacle_grid.launch.py`
  - `livox_ros_driver2_node` と `obstacle_grid_node` を同時起動
- ノード概要:
  - 入力 `PointCloud2` を平面グリッドへ射影
  - `z_min`, `z_max`, `obstacle_min_height` で地面やノイズを除去
  - 占有セルを `nav_msgs/msg/OccupancyGrid` と `visualization_msgs/msg/Marker` で出力
- 主な出力:
  - `obstacle_grid`
  - `obstacle_cells`
- 現在の位置づけ:
  - ローカル障害物可視化の最小実装
  - Nav2 接続前の前段実験として分かりやすい

### 3) livox_ros_driver2
- パス: `src/drivers/livox_ros_driver2`
- 役割:
  - Livox HAP の実機入力を ROS 2 点群へ変換するセンサドライバ
- 現在の使われ方:
  - `adas_bringup` と `obstacle_grid` の両方から起動される
  - 現在の LiDAR 系システムの共通入口

### 4) realsense2_camera / realsense2_camera_msgs / realsense2_description
- パス: `src/drivers/realsense-ros/*`
- 役割:
  - Intel RealSense 公式 ROS 2 ドライバ群
- 現在の使われ方:
  - `rs-launch` スクリプト経由で `realsense2_camera` の launch を使う前提
  - `realsense_packages` の入力元として想定されている

### 5) RTAB-Map 群
- パス: `src/slam/rtabmap_ros/*`
- 主なパッケージ:
  - `rtabmap_odom`, `rtabmap_slam`, `rtabmap_util`, `rtabmap_launch`, `rtabmap_viz` など
- 現在の位置づけ:
  - SLAM / odometry / 可視化のための大型外部スタック
  - 現時点の `adas_bringup` からは未接続
  - 今後、自己位置推定や地図化が必要になったときの候補

### 5.5) FAST-LIO
- パス: `src/slam/fast_lio_ros2`
- パッケージ名: `fast_lio`
- ビルドシステム: `ament_cmake`
- 役割:
  - LiDAR-IMU 融合による局所自己位置推定
  - shadow-mode の ego 側基準となる LiDAR odometry を供給
- 主入力:
  - Livox 系では `livox_ros_driver2/CustomMsg`
  - IMU (`sensor_msgs/msg/Imu`)
- 主出力:
  - `/Odometry` (`nav_msgs/msg/Odometry`)
  - `/path` (`nav_msgs/msg/Path`)
  - `/cloud_registered`
  - `/cloud_registered_body`
  - `/Laser_map`
- 主な launch:
  - `launch/mapping.launch.py`
  - config は `config/mid360.yaml` などを切り替えて使用
- 実装メモ:
  - `laserMapping.cpp` 内で `pubOdomAftMapped_` が `/Odometry` を publish
  - `shadow_mode_ego_estimation` はこの `/Odometry` を入力に使う前提で揃えてある

### 6) Navigation2 群
- パス: `src/slam/navigation2/*`
- 主なパッケージ:
  - `nav2_planner`, `nav2_controller`, `nav2_costmap_2d`, `nav2_bt_navigator`, `nav2_map_server` など
- 現在の位置づけ:
  - フルの経路計画・制御系スタックとして同梱
  - 今のワークスペースではまだ常用経路には入っていない
  - `obstacle_grid` や将来の shadow-mode 評価系と接続する余地は大きい

### 7) MediaPipe ROS 2 群
- パス: `src/img_proc/mediapipe_ros2_suite/src/*`
- 主なパッケージ:
  - `mediapipe_ros2_node`
  - `mediapipe_ros2_py`
  - `mediapipe_ros2_interfaces`
- 現在の位置づけ:
  - 画像処理系の追加実験基盤
  - 現行の Livox / RealSense 中心導線とは未接続

## Shadow-mode 設計メモ

### 現時点の前提
- shadow-mode 実装は基本的に C++ で進める。
- 実車のステアリング値やアクセル/ブレーキ値は CAN から取得できない前提とする。
- そのため、shadow-mode の比較対象は「実操作量」ではなく「実車挙動の推定値」とする。

### 予定している最小パッケージ構成
- `shadow_mode_virtual_control`
  - LiDAR ベースの車線/境界情報から仮想経路と仮想操舵 proxy を生成する
- `shadow_mode_ego_estimation`
  - 実車の移動結果から ego 挙動を推定する
- `shadow_mode_metrics`
  - 仮想判断と実車挙動推定の差分を評価し、CSV/JSON 等へ保存する
- `shadow_mode_bringup`
  - replay / live 用 launch をまとめる

### `shadow_mode_ego_estimation` の入力方針
- `shadow_mode_ego_estimation` の主入力は、FAST-LIO の局所ローカライゼーションから取得した LiDAR オドメトリとする。
- つまり ego 側の推定は、GNSS 単独や CAN 由来ではなく、まず `FAST-LIO` の odometry を基準に設計する。
- 想定用途:
  - 実車の自己軌跡推定
  - 速度・ヨー変化・曲率の推定
  - 仮想経路との比較基準生成

### `shadow_mode_ego_estimation` の想定入出力
- 入力候補:
  - FAST-LIO の `nav_msgs/msg/Odometry`
  - 必要に応じて `sensor_msgs/msg/Imu`
- 出力候補:
  - `/shadow/ego_path`
  - `/shadow/ego_speed`
  - `/shadow/ego_yaw_rate`
  - `/shadow/ego_curvature`

### 実装済み shadow-mode パッケージ
- `src/shadow_mode/shadow_mode_ego_estimation`
  - FAST-LIO の `/Odometry` を主入力にした C++ ノード雛形を追加済み
  - 現在の出力:
    - `/shadow/ego/path`
    - `/shadow/ego/speed`
    - `/shadow/ego/yaw_rate`
    - `/shadow/ego/curvature`
    - `/shadow/ego/debug_markers`
- `src/shadow_mode/shadow_mode_virtual_control`
  - `/livox/lane_detection/scan` を入力にした C++ ノード雛形を追加済み
  - 現在の処理:
    - LaserScan から左右境界を前方距離ビンごとに集約
    - centerline を仮想経路として生成
    - Pure Pursuit 風に仮想操舵 proxy と仮想曲率を算出
    - 境界欠損率と経路曲率 proxy から warning score を算出
  - 現在の出力:
    - `/shadow/virtual/path`
    - `/shadow/virtual/steering_proxy`
    - `/shadow/virtual/curvature`
    - `/shadow/virtual/warning_score`
    - `/shadow/virtual/debug_markers`

### 現在の進捗まとめ
- shadow-mode の最小骨格として、`ego_estimation` と `virtual_control` の2パッケージを追加済み。
- `ego_estimation` は FAST-LIO の `/Odometry` を入力にし、実車挙動の推定値を publish する段階まで到達。
- `virtual_control` は `/livox/lane_detection/scan` を入力にし、仮想経路・仮想操舵 proxy・warning score を publish する段階まで到達。
- まだ metrics / replay 統合 / 実ビルド確認は未完了。

### 次に行う作業
1. Docker 環境で `colcon build --symlink-install` が通るか確認する。
2. `shadow_mode_ego_estimation` と `shadow_mode_virtual_control` のビルドエラーがあれば修正する。
3. `shadow_mode_metrics` を追加し、以下の差分指標を保存できるようにする。
   - `virtual_path` vs `ego_path`
   - `virtual_curvature` vs `ego_curvature`
   - `warning_score`
4. その後 `shadow_mode_bringup` を追加し、bag replay から一発起動できる launch をまとめる。

### 直近の確認ポイント
- 新規 C++ パッケージ:
  - `src/shadow_mode/shadow_mode_ego_estimation`
  - `src/shadow_mode/shadow_mode_virtual_control`
- 依存追加後の Docker 再ビルドが必要。
- この環境では `colcon` 未導入のため、ローカルではビルド未確認。

### 比較指標の基本方針
- CAN ベースの実操舵角比較は行わない。
- 代わりに以下を比較する。
  - 仮想経路 vs 実軌跡
  - 仮想曲率 vs 実曲率
  - レーン中心からの逸脱 proxy
  - heading error

## 既存起動/ビルドスクリプト要点
- `build.sh`
  - `src/drivers/livox_ros_driver2/build.sh humble` を呼び出す
  - `AMARANTHUS_COLCON_PARALLEL_WORKERS=1` をデフォルトにし、メモリ安全側のビルド設定を使う
- `rs-subscriber`
  - `colcon build --symlink-install --packages-select realsense_packages`
  - `ros2 run realsense_packages realsense-sample`
- `rs-launch`
  - `realsense2_camera` の `rs_launch.py` を実行
- `startup.sh`
  - `source install/setup.bash`

## Gitメモ
- `.gitmodules`:
  - `src/drivers/pointcloud_to_laserscan`
  - `src/drivers/realsense-ros`
  - `src/slam/rtabmap_ros`
- Docker イメージは `gazebo_ros_pkgs` を含む前提になったため、依存変更後は `bash docker_build.sh` で再ビルドが必要
- 現在のワークツリーはクリーンではない（既存変更あり）

## 次回開始時の最短手順
1. ROS2環境を有効化（必要なら `source install/setup.bash`）
2. GUI確認なら `cd gui && uv sync && uv run main.py`
3. RealSense確認なら `./rs-subscriber` または `./rs-launch`
4. 障害物グリッド確認なら `ros2 launch obstacle_grid obstacle_grid.launch.py`

## 作業ルール（合意済み）
1. 作業範囲
   - 編集可能範囲は以下とする。
     - `fis-teria` 由来のパッケージ
     - このリポジトリで管理しているソースコード
   - 上記以外の場所で作業する場合は、実施前に必ず確認を取る。

2. ブランチ運用
   - `master` への直接 push は禁止。
   - 変更は `develop` に集約する。
   - 新機能追加は `feature/*` ブランチを作成して作業する。

3. コミット粒度・メッセージ規約
   - 粒度は「1コミット1意図」。
   - コミットメッセージ規約:
     - `Fix:` エラーなどの修正
     - `Update:` 既存コードの更新（ロジック変更など）
     - `Add:` 新しいパッケージの追加

4. 完了条件（Definition of Done）
   - Docker内環境で `colcon build --symlink-install` が完了すること。
   - `colcon build` 実行時は `--symlink-install` を必須とする。

5. 開発開始時の実行手順
   - 開発作業は必ず `autonomous-env.sh` でDockerを起動してから行う。

6. 依存更新
   - 依存更新（`apt` / `pip` / `rosdep` など）は事前確認を必須とする。
   - 確認時には「必要な理由」を明示する。

7. ハード依存作業
   - ハード依存の検証は、ダミーデータまたはログ再生を使って実施する。

8. 問題発生時の復旧方針
   - 修復不可能な問題が発生した場合は、最新コミット時点まで戻す。
