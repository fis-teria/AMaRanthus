# e2e_transfuser

`e2e_transfuser` は、LEAD / TransFuser V6 系モデルを ROS 2 shadow-mode 評価へ接続するための ADAS パッケージです。

初期実装では実車制御 command を publish せず、camera + optional LiDAR + odometry + route proxy から `/shadow/e2e/*` に仮想 E2E 出力を publish します。

`sensor_input_mode` は `auto` / `camera_lidar` / `camera_only` を選べます。デフォルトの `auto` では E2E 用 pointcloud topic (`shadow_mode_e2e_transfuser.launch.py` では `/cloud_registered_body`) が `input_timeout_sec` より古くなったときに camera-only として入力待ちを継続し、`/shadow/e2e/status` の `active_sensor_input_mode` と `missing_optional_inputs` で現在の状態を確認できます。camera-only では LiDAR 由来の odometry や route target も任意入力に落とし、画像と camera_info だけで mock E2E 出力を維持します。

`shadow_mode_e2e_transfuser.launch.py` はデフォルトで YOLO も起動します。`/yolo/detections` を `e2e_path_overlay` が購読し、overlay 画像へ検出bboxを重ねます。tracking node は追加のフル解像度画像購読を避けるため既定で `yolo_use_tracking:=false` にしています。debug image node は重さを避けるため `yolo_use_debug:=false` にしています。YOLO は既定で `Data/venvs/yolo_ros_cuda` の CUDA 対応 Torch と `Data/models/yolo/yolo11n.pt` を使い、`yolo_device:=cuda:0` で起動します。GPU を使わない場合は `yolo_device:=cpu` を指定してください。

`shadow_mode_e2e_transfuser.launch.py` は E2E 10Hz 経路を優先するため、デフォルトでは Livox lane detection を起動せず、カメラ白線検知のみ起動します。Livox lane detection を試す場合は `use_livox_lane_detection:=true` を指定してください。Livox driver は `camera_lidar_bringup` 側で起動するため、E2E から呼び出す `livox_lane_detection_live.launch.py` では `launch_livox_driver:=false` に固定しています。Livox lane detection は既定で scan-only、`lane_detection_max_process_rate_hz:=5.0`、`lane_detection_device:=cuda:0` です。CUDA が使えない libtorch/runtime では CPU に fallback します。`use_adas_bringup:=true` でフル ADAS bringup 側から Livox lane detection を起動する場合も、二重起動を避けるため `use_livox_lane_detection:=false` を併用してください。

`livox_lane_detection` は C++ TorchScript node なので、ビルドと実行は `/opt/libtorch` を使います。Python wheel の `Data/venvs/yolo_ros_cuda/.../torch/lib` と混ぜると `libc10_cuda.so` の symbol lookup error が出るため、E2E launch は `lane_detection_torch_lib_path:=/opt/libtorch/lib` を既定で lane detection node の `LD_LIBRARY_PATH` 先頭に入れます。

`shadow_mode_e2e_transfuser.launch.py` はデフォルトで ADAS description と FAST-LIO も単独起動します。description は `use_adas_description:=true` で `adas_robot_state_publisher` を起動し、`adas_livox.urdf` から `base_link` / `livox_frame` / `camera0` の TF を publish します。FAST-LIO は `use_fast_lio:=true` で `fast_lio` の `mapping.launch.py` を起動し、既定では `/Odometry` を E2E と shadow ego estimation の共通 odometry 入力にします。`shadow_virtual_control` は `virtual_input_mode:=pointcloud` のまま FAST-LIO の `/cloud_registered` を使います。

V4L2 カメラは既定で Tier IV C2 profile を使います。USB 差し替えで `/dev/video0` が別カメラになる場合は、`use_v4l2_preflight:=true` により `TIER IV` または `GMSL2-USB3.0 Conversion Kit` に合う Video Capture デバイスを自動選択します。明示固定したい場合は `v4l2_video_device:=/dev/v4l/by-id/...` または `/dev/v4l/by-path/...` を指定してください。誤デバイスで続行したくない場合は `v4l2_strict_device_check:=true` を併用してください。

10Hz の GUI 表示を優先する場合は `camera_output_encoding:=yuv422` を指定できます。GMSL2 カメラの `UYVY` を ROS へそのまま `yuv422` として流し、E2E runtime / overlay / GUI 側で必要なときだけ RGB へ変換します。`E2E_LIGHTWEIGHT_PRESET=fp16_minimal` は `camera_output_encoding:=yuv422` と `use_yolo:=false` を自動で設定します。

`shadow_mode_e2e_transfuser.launch.py` の E2E runtime は既定で `lead_python` です。`Data/src/lead` と `Data/models/tfv6/tfv6_resnet34` がある場合、`Data/venvs/yolo_ros_cuda` の CUDA 対応 PyTorch を使って `runtime_device:=cuda:0` で LEAD / TFv6 をロードします。推論時は `disable_aux_heads:=true` を既定にして、semantic / depth / BEV semantic / bbox / radar detection など学習時の補助ヘッドは構築しません。旧mock経路に戻す場合は `e2e_runtime_mode:=mock` を指定してください。

`e2e_path_overlay` は E2E model input を既定で `front_center_stitched` layout にします。LEAD の 3-camera stitched 入力に近づけるため、単眼 front camera を `1152x384` 全体へ横伸ばしせず、中央の `384x384` slot に center crop して配置します。旧来の単純 resize へ戻して比較する場合は `e2e_model_input_layout:=resize` を指定してください。

リプレイで画像 topic はあるが `camera_info` が bag に入っていない場合は、`launch_shadow_mode_e2e_transfuser_replay.sh` が `e2e_synthesize_camera_info_when_missing:=true` を有効にし、画像サイズから暫定 `CameraInfo` を合成します。状態は `/shadow/e2e/status` の `camera_info_source` と `synthetic_camera_info_count` で確認できます。通常 launch では既定無効のため、実機の camera calibration topic を優先します。

LEAD runtime は `lead_lidar_raster_enabled:=true` のとき `PointCloud2` から `rasterized_lidar` を生成します。ROS の `base_link` 系座標 (`x` 前方、`y` 左) を LEAD/CARLA 系 (`x` 前方、`y` 右) に合わせるため、既定で `lead_lidar_flip_y_axis:=true` です。上位 launch では E2E raster 用に `e2e_pointcloud_topic:=/cloud_registered_body` を使い、GUI / virtual control 用の `pointcloud_topic:=/cloud_registered` と分けています。`/shadow/e2e/status` の `lead_lidar_raster` に frame_id、使用点数、非ゼロpixel数が出ます。`lead_lidar_frame_contract` には TF 変換なしで扱ってよい frame かどうかが出ます。既定の許可frameは `body,base_link` です。

LEAD の route target は `/shadow/route/target_path` から 3 点化できます。既定では `use_target_path_triplet:=true` で、停止時は `target_path_previous_distance_m:=5.0`、`target_path_current_distance_m:=15.0`、`target_path_next_distance_m:=25.0` の点を `target_point_previous/current/next` へ渡します。`target_path_speed_adaptive:=true` では `/Odometry` の速度に応じて current 距離を `target_path_speed_lookahead_time_sec:=1.2` 秒分だけ先へ伸ばし、previous/next も同じ比率で伸ばします。Path が無い、古い、または frame が `base_link,body` 以外の場合は従来の `/shadow/route/target_point` 1点へ fallback します。`/shadow/e2e/status` の `lead_target_triplet` で実際に使った source、速度、要求距離、実際に取れた距離、3点座標を確認できます。

入力画像の `UYVY/yuv422 -> RGB` は既定では OpenCV CPU path です。GPU 側で前処理も試す場合は `e2e_input_preprocess_backend:=torch_cuda`、単体 launch では `input_preprocess_backend:=torch_cuda` を指定してください。`/shadow/e2e/status` には `lead_preprocess_latency_ms` と `input_preprocess_backend` が出ます。

## Phase 1: LEAD 環境診断

LEAD repo や checkpoint をまだ配置していない状態でも、診断結果を JSON で確認できます。

```bash
ros2 run e2e_transfuser e2e_transfuser_check_lead.py --dry-run
```

LEAD repo と checkpoint を指定する場合:

```bash
ros2 run e2e_transfuser e2e_transfuser_check_lead.py \
  --lead-project-root /path/to/lead \
  --model-path Data/models/tfv6/tfv6_resnet34 \
  --model-variant tfv6_resnet34
```

`LEAD_PROJECT_ROOT` 環境変数も利用できます。

CUDA forward まで確認する場合:

```bash
ros2 run e2e_transfuser e2e_transfuser_probe_lead.py \
  --lead-project-root Data/src/lead \
  --model-path Data/models/tfv6/tfv6_resnet34 \
  --python-site Data/venvs/yolo_ros_cuda/lib/python3.10/site-packages \
  --torch-lib Data/venvs/yolo_ros_cuda/lib/python3.10/site-packages/torch/lib \
  --device cuda:0 \
  --forward
```

成功時は `loaded: true` と `forward.device: cuda:0`、`path_points` が表示されます。

## Phase 4: 軽量化ベンチマーク導線

Z13 向けには、camera + LiDAR を維持したまま `PyTorch FP32 -> PyTorch FP16 -> TensorRT FP16 -> TensorRT INT8` の順に確認します。

```bash
ros2 run e2e_transfuser e2e_transfuser_benchmark.py \
  --runtime-mode mock \
  --precision-mode fp16 \
  --dry-run
```

INT8 は calibration data と経路差分評価が必要なため、`--allow-int8` を明示した場合だけ検討対象にします。

E2E 入力前処理だけを比較する場合:

```bash
ros2 run e2e_transfuser e2e_preprocess_benchmark.py \
  --lead-project-root Data/src/lead \
  --python-site Data/venvs/yolo_ros_cuda/lib/python3.10/site-packages \
  --torch-lib Data/venvs/yolo_ros_cuda/lib/python3.10/site-packages/torch/lib \
  --device cuda:0 \
  --precision-mode fp16 \
  --forward
```
