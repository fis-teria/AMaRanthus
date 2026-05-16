# e2e_transfuser

`e2e_transfuser` は、LEAD / TransFuser V6 系モデルを ROS 2 shadow-mode 評価へ接続するための ADAS パッケージです。

初期実装では実車制御 command を publish せず、camera + optional LiDAR + odometry + route proxy から `/shadow/e2e/*` に仮想 E2E 出力を publish します。

`sensor_input_mode` は `auto` / `camera_lidar` / `camera_only` を選べます。デフォルトの `auto` では `/livox/lidar` が `input_timeout_sec` より古くなったときに camera-only として入力待ちを継続し、`/shadow/e2e/status` の `active_sensor_input_mode` と `missing_optional_inputs` で現在の状態を確認できます。camera-only では LiDAR 由来の odometry や route target も任意入力に落とし、画像と camera_info だけで mock E2E 出力を維持します。

`shadow_mode_e2e_transfuser.launch.py` はデフォルトで YOLO も起動します。`/yolo/tracking` を `e2e_path_overlay` が購読し、overlay 画像へ検出bboxを重ねます。debug image node は重さを避けるため `yolo_use_debug:=false` にしています。YOLO は既定で `Data/venvs/yolo_ros_cuda` の CUDA 対応 Torch と `Data/models/yolo/yolo11n.pt` を使い、`yolo_device:=cuda:0` で起動します。GPU を使わない場合は `yolo_device:=cpu` を指定してください。

`shadow_mode_e2e_transfuser.launch.py` はデフォルトで Livox lane detection も起動します。Livox driver は `camera_lidar_bringup` 側で起動するため、E2E から呼び出す `livox_lane_detection_live.launch.py` では `launch_livox_driver:=false` に固定しています。lane detection だけ止めたい場合は `use_livox_lane_detection:=false` を指定してください。`use_adas_bringup:=true` でフル ADAS bringup 側から lane detection を起動する場合も、二重起動を避けるため `use_livox_lane_detection:=false` を併用してください。

`livox_lane_detection` は C++ TorchScript node なので、ビルドと実行は `/opt/libtorch` を使います。Python wheel の `Data/venvs/yolo_ros_cuda/.../torch/lib` と混ぜると `libc10_cuda.so` の symbol lookup error が出るため、E2E launch は `lane_detection_torch_lib_path:=/opt/libtorch/lib` を既定で lane detection node の `LD_LIBRARY_PATH` 先頭に入れます。

`shadow_mode_e2e_transfuser.launch.py` はデフォルトで ADAS description と FAST-LIO も単独起動します。description は `use_adas_description:=true` で `adas_robot_state_publisher` を起動し、`adas_livox.urdf` から `base_link` / `livox_frame` / `camera0` の TF を publish します。FAST-LIO は `use_fast_lio:=true` で `fast_lio` の `mapping.launch.py` を起動し、既定では `/Odometry` を E2E と shadow ego estimation の共通 odometry 入力にします。`shadow_virtual_control` は `virtual_input_mode:=pointcloud` のまま `/livox/lidar` を使います。

V4L2 カメラは既定で Tier IV C2 profile を使います。USB 差し替えで `/dev/video0` が別カメラになる場合は、`v4l2_video_device:=/dev/v4l/by-id/...` または `/dev/v4l/by-path/...` を指定してください。`use_v4l2_preflight:=true` では `v4l2-ctl --info` を起動前に確認し、`v4l2_expected_device_name:=TIER IV` と合わない場合は警告します。誤デバイスで続行したくない場合は `v4l2_strict_device_check:=true` を併用してください。

`shadow_mode_e2e_transfuser.launch.py` の E2E runtime は既定で `lead_python` です。`Data/src/lead` と `Data/models/tfv6/tfv6_resnet34` がある場合、`Data/venvs/yolo_ros_cuda` の CUDA 対応 PyTorch を使って `runtime_device:=cuda:0` で LEAD / TFv6 をロードします。推論時は `disable_aux_heads:=true` を既定にして、semantic / depth / BEV semantic / bbox / radar detection など学習時の補助ヘッドは構築しません。旧mock経路に戻す場合は `e2e_runtime_mode:=mock` を指定してください。

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
