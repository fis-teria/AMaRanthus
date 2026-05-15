# shadow_mode_replay_tools

`shadow_mode_replay_tools` は、rosbag replay から shadow-mode 評価を同じ手順で繰り返すための補助パッケージです。

CAN / OBD の実 driver input は使わず、`/Odometry` から車速・曲率・操舵 proxy を推定する現在の方針に合わせています。

## Usage

```bash
ros2 run shadow_mode_replay_tools shadow_mode_replay.py \
  --bag Data/rosbag/sample_drive \
  --scenario sample_drive
```

既定では以下を行います。

- `shadow_mode_bringup` を `use_adas_bringup:=false` で起動する
- `ros2 bag play --clock` で bag を再生する
- metrics CSV を `Data/shadow_mode_runs/<timestamp>_<scenario>/metrics/shadow_mode_metrics.csv` に保存する
- shadow-mode 評価 topic を `Data/shadow_mode_runs/<timestamp>_<scenario>/rosbag/shadow_mode_bag` に記録する
- 実行時のコマンドと設定を `run_metadata.json` に保存する

3D PointCloud2 を仮想制御入力にする場合:

```bash
ros2 run shadow_mode_replay_tools shadow_mode_replay.py \
  --bag Data/rosbag/sample_drive \
  --scenario sample_drive_pointcloud \
  --virtual-input-mode pointcloud \
  --pointcloud-topic /livox/lidar
```

CSV だけ保存し、shadow bag の再記録を止める場合:

```bash
ros2 run shadow_mode_replay_tools shadow_mode_replay.py \
  --bag Data/rosbag/sample_drive \
  --scenario sample_drive \
  --no-record-shadow-bag
```

実行せずにコマンドだけ確認する場合:

```bash
ros2 run shadow_mode_replay_tools shadow_mode_replay.py \
  --bag Data/rosbag/sample_drive \
  --scenario sample_drive \
  --dry-run
```
