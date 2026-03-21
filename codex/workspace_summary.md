# Codex Workspace Summary

更新日: 2026-03-21

## ペアコーディング時の性格設定
- アシスタント性格: ロボティクスを専門にしているオタクにやさしいギャル
- 期待する進め方:
  - ロボティクス文脈を優先して判断
  - こまめに進捗共有
  - 実装と説明をセットで進行

## ワークスペース構成（`/home/hellbore/AMaRanthus`）
- `gui/`: PyQt5 + WebEngine ベースのGUI
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

### 1) realsense_packages
- パス: `src/realsense_app/realsense_packages`
- ビルドシステム: `ament_cmake`
- 主依存:
  - `rclcpp`, `sensor_msgs`, `std_msgs`, `message_filters`, `cv_bridge`
  - `realsense2`（CMakeでは `find_package(realsense2 2.54.2)`）
- 生成実行ファイル（CMakeLists）:
  - `realsense-sample`
  - `realsense_laser_scan`

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

## 既存起動/ビルドスクリプト要点
- `rs-subscriber`
  - `colcon build --symlink-install --packages-select realsense_packages`
  - `ros2 run realsense_packages realsense-sample`
- `rs-launch`
  - `realsense2_camera` の `rs_launch.py` を実行
- `startup.sh`
  - `source install/setup.bash`

## Gitメモ
- `.gitmodules`:
  - `src/drivers/realsense-ros`
  - `src/slam/rtabmap_ros`
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

5. 依存更新
   - 依存更新（`apt` / `pip` / `rosdep` など）は事前確認を必須とする。
   - 確認時には「必要な理由」を明示する。

6. ハード依存作業
   - ハード依存の検証は、ダミーデータまたはログ再生を使って実施する。

7. 問題発生時の復旧方針
   - 修復不可能な問題が発生した場合は、最新コミット時点まで戻す。
