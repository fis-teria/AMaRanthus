# LEAD / TransFuser ROS 2 パッケージ仕様書

作成日: 2026-05-13

## 1. 目的

この仕様書は、LEAD の TransFuser V6 / TFv6 系モデルをベースに、Helianthus / AMaRanthus の ROS 2 shadow-mode 環境で End-to-End 走行判断を評価するための ROS 2 パッケージ仕様を定義する。

最終目標は、軽量化した TransFuser 系 End-to-End モデルを実車または rosbag replay のセンサ入力で動かし、車両を直接制御せずに `/shadow/e2e/...` 配下へ仮想 trajectory / control / confidence / debug 情報を publish することである。

本仕様では、最初から実車制御へ接続せず、既存の `shadow_mode` 評価基盤へ E2E モデル出力を追加する。これにより、従来の LiDAR/FAST-LIO ベースの shadow virtual control と、LEAD/TransFuser ベースの E2E 出力を同じ replay と metrics の流れで比較できるようにする。

## 2. 背景

### 2.1 LEAD / TFv6

LEAD は CARLA Leaderboard 2.0 / Bench2Drive 向けの End-to-End driving stack であり、TransFuser V6 系の checkpoint と評価コードを提供する。

2026-05-13 時点で公開情報から確認した前提は以下である。

- 公式実装は Python ベースの CARLA 評価スタックであり、ROS 2 パッケージではない
- checkpoint は Hugging Face の `ln2697/tfv6` で公開されている
- `tfv6_resnet34`、`tfv6_regnety032`、`visiononly_resnet34` など複数 variant がある
- 実行環境は Python 3.10、CARLA 0.9.15、CUDA / PyTorch 系依存を前提にしている
- 入力・座標系・route 表現は CARLA / LEAD の評価 harness に強く結びついている

### 2.2 Autoware の E2E 実装参考

Autoware Universe には `autoware_tensorrt_vad` があり、VAD モデルを TensorRT 最適化した ROS 2 コンポーネントとして実装している。

この仕様では TransFuser そのものではなく LEAD/TFv6 を対象にするが、ROS 2 統合設計では `autoware_tensorrt_vad` の以下の考え方を参考にする。

- ROS topic 入出力層とモデル推論層を分離する
- モデル設定とデプロイ設定を分離する
- 入力 topic 名や camera mapping は parameter で差し替える
- 出力は Autoware / shadow-mode が扱いやすい trajectory / object / debug 表現へ変換する

## 3. 非目標

初期フェーズでは以下を行わない。

- 実車の steer / accel / brake actuator へ直接 command を送る
- 公道での自律走行
- LEAD の学習 pipeline 全体を ROS 2 パッケージ内へ移植する
- CARLA Leaderboard 2.0 の全機能を ROS 2 から再現する
- いきなり TensorRT / ONNX 化を必須にする
- HD map 前提の完全な Autoware planning 置換
- 安全認証や量産 ADAS 相当の保証

## 4. 全体方針

### 4.1 段階的な到達点

| フェーズ | 目的 | 成果物 |
| --- | --- | --- |
| Phase 0 | 仕様確定と依存調査 | 本仕様書、topic 契約、入力不足リスト |
| Phase 1 | LEAD checkpoint のオフライン推論を確認 | ROS 2 外で TFv6 inference が動く検証ログ |
| Phase 2 | ROS 2 wrapper MVP | `e2e_transfuser` が camera + LiDAR + odometry の mock / replay 入力から `/shadow/e2e/*` を publish |
| Phase 3 | ShadowMode metrics 連携 | E2E 出力と既存 virtual control / ego proxy の比較 |
| Phase 4 | 軽量化 | camera + LiDAR を維持したまま FP16 / TensorRT / 補助 head 無効化を検討 |
| Phase 5 | 実車 replay 評価 | Livox / camera / odometry bag から repeatable evaluation |

### 4.2 初期パッケージ名と配置

初期 ROS 2 パッケージ名は `e2e_transfuser` とし、配置先は `amaranthus/src/adas/e2e_transfuser` とする。

理由:

- LEAD / TransFuser は ADAS の判断モデルとして扱うため、`src/adas` 配下の方が責務が自然
- パッケージ名を短くし、将来的に shadow-mode 以外の評価や Autoware adapter からも再利用しやすくする
- 実車制御へ直結しないことは package 名ではなく、出力 topic を `/shadow/e2e/*` に限定することで明示する

LEAD のコード自体は ROS 2 パッケージ内に丸ごとコピーせず、外部依存または vendor 配置として扱う。パッケージは LEAD の推論 entrypoint を呼び出す adapter に徹する。

## 5. 想定ディレクトリ構成

```text
amaranthus/src/adas/e2e_transfuser/
  CMakeLists.txt
  package.xml
  README.md
  launch/
    e2e_transfuser.launch.py
  config/
    e2e_transfuser.param.yaml
  scripts/
    e2e_transfuser_node.py
  e2e_transfuser/
    __init__.py
    lead_adapter.py
    input_buffer.py
    output_converter.py
    model_runtime.py
    mock_runtime.py
```

Python package として実装し、`ament_python` または `ament_cmake` + Python script install のどちらかを採用する。既存 `shadow_mode_replay_tools` は `ament_cmake` で script install しているため、初期実装は repo の流儀に合わせて `ament_cmake` + `install(PROGRAMS ...)` でもよい。

## 6. ノード仕様

### 6.1 `e2e_transfuser_node`

目的:

- ROS 2 topic から camera / LiDAR / odometry / route hint を受け取る
- LEAD/TFv6 の推論入力へ変換する
- 推論結果を shadow-mode 用 topic に変換して publish する
- 推論できない場合でも、入力欠損・モデル未ロード・座標変換未対応などを diagnostics と summary に出す

### 6.2 入力 topic

初期 MVP では「本物の LEAD 入力を完全再現する」よりも、「ROS 2 側の契約を固めて欠損を可視化する」ことを優先する。

| Topic | 型 | 必須 | 説明 |
| --- | --- | --- | --- |
| `/sensing/camera/camera0/image_rect_color` | `sensor_msgs/msg/Image` | Phase 2 必須 | 前方カメラ画像。初期は 1 camera mainline |
| `/sensing/camera/camera0/camera_info` | `sensor_msgs/msg/CameraInfo` | Phase 2 必須 | 前方カメラ内部パラメータ |
| `/livox/lidar` | `sensor_msgs/msg/PointCloud2` | Phase 2 必須 | LiDAR 点群。TransFuser の camera + LiDAR fusion を維持するため初期契約に含める |
| `/Odometry` | `nav_msgs/msg/Odometry` | Phase 2 必須 | ego pose / velocity の基準 |
| `/shadow/route/target_point` | `geometry_msgs/msg/PointStamped` | Phase 2 推奨 | E2E モデルへ渡す目標点 proxy |
| `/shadow/route/command` | `std_msgs/msg/String` | Phase 3 以降 | lane follow / left / right などの high-level command proxy |

将来、LEAD/TFv6 の本来の multi-camera / route 入力へ近づける場合は、以下を追加する。

| Topic | 型 | 説明 |
| --- | --- | --- |
| `/sensing/camera/camera1/image_rect_color` 以降 | `sensor_msgs/msg/Image` | surround camera |
| `/sensing/camera/camera*/camera_info` | `sensor_msgs/msg/CameraInfo` | multi-camera calibration |
| `/map/vector_map` または adapter topic | TBD | route / lane / map context |
| `/localization/kinematic_state` | `nav_msgs/msg/Odometry` | Autoware 側 odometry 互換入力 |

### 6.3 出力 topic

| Topic | 型 | 説明 |
| --- | --- | --- |
| `/shadow/e2e/path` | `nav_msgs/msg/Path` | E2E が予測した waypoint path |
| `/shadow/e2e/trajectory` | `autoware_planning_msgs/msg/Trajectory` または `nav_msgs/msg/Path` | Autoware 互換 trajectory。依存が重い場合は Phase 2 では `Path` のみ |
| `/shadow/e2e/steering_proxy` | `std_msgs/msg/Float32` | waypoint から推定した操舵 proxy `[rad]` |
| `/shadow/e2e/curvature` | `std_msgs/msg/Float32` | 予測 path の曲率 `[1/m]` |
| `/shadow/e2e/speed_target` | `std_msgs/msg/Float32` | E2E の目標速度 proxy `[m/s]` |
| `/shadow/e2e/confidence` | `std_msgs/msg/Float32` | 推論成立度。入力欠損や stale 入力で低下 |
| `/shadow/e2e/status` | `std_msgs/msg/String` | JSON status。model loaded / input ready / latency など |
| `/shadow/e2e/debug_markers` | `visualization_msgs/msg/MarkerArray` | RViz / GUI 用 marker |

Phase 2 では Autoware message 依存を必須にしない。まず `nav_msgs/msg/Path` と `std_msgs` で評価可能にし、Phase 3 以降で `autoware_planning_msgs/msg/Trajectory` を追加する。

### 6.4 Status JSON

`/shadow/e2e/status` は `std_msgs/msg/String` に JSON を入れる。

例:

```json
{
  "stamp": 1778598000.123,
  "model": "tfv6_resnet34",
  "runtime": "lead_python",
  "model_loaded": true,
  "input_ready": true,
  "missing_inputs": [],
  "latency_ms": 86.4,
  "confidence": 0.82,
  "frame_id": "base_link",
  "mode": "shadow_only"
}
```

## 7. LEAD adapter 仕様

### 7.1 分離レイヤー

`e2e_transfuser` は以下の 3 層に分ける。

| 層 | 役割 |
| --- | --- |
| ROS layer | subscribe / publish / parameter / QoS / diagnostics |
| Adapter layer | ROS message と LEAD 入力・出力の変換 |
| Runtime layer | LEAD Python 推論、mock 推論、将来の ONNX/TensorRT 推論 |

この分離により、最初は mock runtime で ROS 2 契約だけを固め、後から LEAD runtime を接続できる。

### 7.2 Runtime mode

| mode | 説明 | 用途 |
| --- | --- | --- |
| `mock` | 入力 odometry と target point から単純な path を返す | ROS 2 topic 契約・GUI・metrics の先行実装 |
| `lead_python` | LEAD の PyTorch checkpoint を直接呼び出す | 最初の本命推論 |
| `onnx` | export した ONNX を呼び出す | 軽量化検証 |
| `tensorrt` | TensorRT engine を呼び出す | Jetson / 車載 GPU 向け |

Phase 2 の acceptance は `mock` でよい。Phase 3 以降で `lead_python` を接続する。

## 8. パラメータ仕様

| パラメータ | 既定値 | 説明 |
| --- | --- | --- |
| `runtime_mode` | `mock` | `mock`, `lead_python`, `onnx`, `tensorrt` |
| `model_variant` | `tfv6_resnet34` | 使用 checkpoint variant |
| `model_path` | `Data/models/tfv6/tfv6_resnet34` | checkpoint または model directory |
| `lead_project_root` | `""` | LEAD repo path。空なら環境変数 `LEAD_PROJECT_ROOT` を使う |
| `image_topic` | `/sensing/camera/camera0/image_rect_color` | main camera image |
| `camera_info_topic` | `/sensing/camera/camera0/camera_info` | main camera info |
| `pointcloud_topic` | `/livox/lidar` | LiDAR input |
| `odom_topic` | `/Odometry` | ego odometry input |
| `target_point_topic` | `/shadow/route/target_point` | route target proxy |
| `output_frame` | `base_link` | 出力 path frame |
| `publish_rate_hz` | `10.0` | 推論・publish 周期 |
| `input_timeout_sec` | `0.5` | 入力 stale 判定 |
| `max_waypoints` | `10` | 出力 waypoint 数 |
| `wheel_base_m` | `2.7` | steering proxy 推定に使う wheelbase |
| `enable_debug_markers` | `true` | marker 出力 |
| `enable_autoware_trajectory` | `false` | Autoware trajectory 出力を有効化 |

## 9. ShadowMode 連携

### 9.1 既存 pipeline との関係

既存 `shadow_mode` は以下を持つ。

- `/shadow/ego/*`: FAST-LIO などの odometry から ego state を推定
- `/shadow/virtual/*`: LiDAR / lane scan から仮想制御を生成
- `/shadow/metrics/*`: ego proxy と virtual control を比較

E2E 追加後は以下の比較軸を作る。

```text
/Odometry
  -> shadow_mode_ego_estimation
  -> /shadow/ego/*

/livox/lidar or camera
  -> shadow_mode_virtual_control
  -> /shadow/virtual/*

camera / lidar / odometry / route proxy
  -> e2e_transfuser
  -> /shadow/e2e/*

/shadow/ego/* + /shadow/virtual/* + /shadow/e2e/*
  -> shadow_mode_metrics or shadow_mode_e2e_metrics
  -> /shadow/metrics/*
```

### 9.2 Metrics 拡張案

初期は既存 `shadow_mode_metrics` を壊さず、E2E 専用比較は別ノード `shadow_mode_e2e_metrics` として追加する。

| 出力 | 型 | 説明 |
| --- | --- | --- |
| `/shadow/metrics/e2e_steering_delta` | `std_msgs/msg/Float32` | `e2e_steering - driver_proxy` |
| `/shadow/metrics/e2e_virtual_steering_delta` | `std_msgs/msg/Float32` | `e2e_steering - virtual_steering` |
| `/shadow/metrics/e2e_curvature_delta` | `std_msgs/msg/Float32` | `e2e_curvature - ego_curvature` |
| `/shadow/metrics/e2e_intervention_score` | `std_msgs/msg/Float32` | E2E 出力差分と confidence を合成した score |
| `/shadow/metrics/e2e_summary` | `std_msgs/msg/String` | JSON summary |

## 10. 軽量化方針

### 10.1 優先順

軽量化は camera + LiDAR fusion を維持したまま進める。初期方針では vision-only / camera-only へ逃がさない。LiDAR は近距離安全確認だけでなく TransFuser の主入力として残し、軽量化は runtime、補助 head、ensemble、精度表現、モデル構造の順で段階化する。

Z13 の現実的な forward 推論目標は以下とする。

| 段階 | 目標 | 採用判断 |
| --- | --- | --- |
| PyTorch FP32 | まず動作確認。VRAM 8GB 内に収める | baseline。遅くてもよい |
| PyTorch FP16 | `batch=1` で安定推論。VRAM と latency を測る | 最初の実用候補 |
| TensorRT FP16 | 10Hz 級を安定させることを狙う | Z13 実用化の主目標 |
| TensorRT INT8 | FP16 との経路差分が許容範囲なら採用検討 | 最後に比較。初期採用しない |

INT8 は最初から行わない。TensorRT INT8 はモデルサイズ削減・高速化に有効だが、PTQ では代表的な calibration data が必要で、複雑な連続値出力モデルでは精度低下が起き得る。TransFuser は分類だけでなく waypoint / target speed / control proxy に関わる連続値を出すため、INT8 化で経路が微妙にずれる可能性がある。まず FP16 を基準にし、その後 INT8 の経路差分を評価する。

軽量化で触る順番:

1. 補助 head を切る。semantic / depth / detection / BEV semantic などが推論時の制御出力に不要なら計算しない。再学習なしで効く可能性があるため最初に確認する。
2. ensemble を使わない。公式評価では複数 `.pth` を同じ checkpoint directory に置くと ensemble できるが、Z13 では単一 checkpoint 推論に固定する。
3. FP16 固定化。PyTorch AMP で安定性を確認し、問題がなければ ONNX / TensorRT FP16 engine 化へ進む。
4. 入力解像度または LiDAR BEV grid を下げる。効果は大きいが、学習時の視野・解像度・LiDAR grid に依存するため、原則 fine-tuning または再学習を前提にする。
5. Transformer / fusion backbone を小さくする。`n_layer`、token dim、backbone channel 数を下げる変更は学習済み重みをそのまま使えないため、後段の distillation 対象にする。
6. INT8 を比較する。calibration data を用意し、FP16 との差分を path / steering / curvature / intervention score で評価してから採用を判断する。

### 10.2 実車向け優先事項

Livox HAP のダッシュボード配置で遠方認識に限界がある前提でも、TransFuser 系 E2E では camera + LiDAR を維持する。フロントカメラは遠方認識の主入力、LiDAR は近距離の幾何・障害物・BEV fusion 入力として扱う。

そのため初期 MVP は「front camera + LiDAR BEV + odometry + target point」を mainline とする。camera-only / vision-only は軽量化の本線ではなく、比較実験または緊急 fallback として扱う。

### 10.3 Backbone 変更方針

LEAD/TFv6 の backbone は `timm.create_model()` で `image_architecture` と `lidar_architecture` を生成する構造である。そのため、ResNet 系から MobileNetV3 系へ置き換えること自体は設計上は可能である。

ただし、MobileNetV3 化は既存 checkpoint の軽量推論ではなく、新しいモデル variant の作成として扱う。

- 既存の `tfv6_resnet34` checkpoint は MobileNetV3 backbone にはそのまま読み込めない
- image / LiDAR encoder の feature channel 数と feature stage が変わるため、fusion transformer、channel adapter、head の重み互換性が崩れる
- LiDAR branch は 1ch または 2ch の BEV pseudo image を入力するため、MobileNetV3 が `features_only=True` と `in_chans=1/2` で安定動作するか確認が必要
- ImageNet pretrained MobileNetV3 を image branch に使うことは候補になるが、LiDAR branch と fusion 部分は fine-tuning / 再学習 / distillation が必要

従って Z13 向けの優先順は、まず ResNet34 系 camera + LiDAR checkpoint を FP16 / TensorRT FP16 で動かし、その後に MobileNetV3 などの小型 backbone を distillation 対象として検討する。

## 11. Bringup 仕様

### 11.1 単体起動

```bash
ros2 launch e2e_transfuser e2e_transfuser.launch.py
```

mock runtime:

```bash
ros2 launch e2e_transfuser e2e_transfuser.launch.py runtime_mode:=mock
```

LEAD Python runtime:

```bash
ros2 launch e2e_transfuser e2e_transfuser.launch.py \
  runtime_mode:=lead_python \
  lead_project_root:=/path/to/lead \
  model_path:=Data/models/tfv6/tfv6_resnet34
```

### 11.2 ShadowMode bringup への統合

`shadow_mode_bringup.launch.py` には将来以下の launch 引数を追加する。

| 引数 | 既定値 | 説明 |
| --- | --- | --- |
| `use_e2e_transfuser` | `false` | E2E TransFuser node を起動する |
| `e2e_runtime_mode` | `mock` | E2E runtime |
| `e2e_model_path` | `Data/models/tfv6/tfv6_resnet34` | model directory |
| `e2e_model_variant` | `tfv6_resnet34` | model variant |
| `use_e2e_metrics` | `false` | E2E metrics node を起動する |

例:

```bash
ros2 launch shadow_mode_bringup shadow_mode_bringup.launch.py \
  use_e2e_transfuser:=true \
  e2e_runtime_mode:=mock
```

## 12. Replay 評価

`shadow_mode_replay_tools` は将来 E2E 引数を透過できるようにする。

例:

```bash
ros2 run shadow_mode_replay_tools shadow_mode_replay.py \
  --bag Data/rosbag/sample_drive \
  --scenario e2e_mock_sample \
  --extra-launch-arg use_e2e_transfuser:=true \
  --extra-launch-arg e2e_runtime_mode:=mock
```

LEAD runtime の replay 評価:

```bash
ros2 run shadow_mode_replay_tools shadow_mode_replay.py \
  --bag Data/rosbag/sample_drive \
  --scenario e2e_tfv6_resnet34 \
  --extra-launch-arg use_e2e_transfuser:=true \
  --extra-launch-arg e2e_runtime_mode:=lead_python \
  --extra-launch-arg e2e_model_path:=Data/models/tfv6/tfv6_resnet34
```

## 13. 受け入れ基準

### Phase 2: ROS 2 wrapper MVP

- `colcon build --packages-select e2e_transfuser` が成功する
- `ros2 launch e2e_transfuser e2e_transfuser.launch.py runtime_mode:=mock` が起動する
- camera / LiDAR / odometry / target point の入力欠損が `/shadow/e2e/status` に出る
- 入力が揃ったとき `/shadow/e2e/path`、`/shadow/e2e/steering_proxy`、`/shadow/e2e/confidence` が publish される
- `record_shadow_bag:=true` または replay tools で `/shadow/e2e/*` を記録できる

### Phase 3: LEAD Python runtime

- `tfv6_resnet34` checkpoint を指定して node が model load できる
- 1 frame または短い sequence で推論が通る
- 推論 latency が `/shadow/e2e/status` に出る
- LEAD の座標系から ROS `base_link` frame への変換方針が文書化される
- 推論失敗時に node が落ちず、status に error reason を出す

### Phase 4: 軽量化

- baseline の PyTorch runtime latency / GPU memory を記録する
- PyTorch FP16 と TensorRT FP16 の latency / memory / output stability を比較する
- single checkpoint、補助 head 無効化、FP16、TensorRT 化、入力縮小などの軽量化効果を CSV または JSON で記録する
- INT8 は FP16 との差分評価を通った場合のみ採用候補にする

## 14. 未確定事項

| 項目 | 現状 | 次アクション |
| --- | --- | --- |
| LEAD の実入力形式 | CARLA harness 依存 | `lead` repo の inference API を実コードで確認 |
| route command | 実車側に CARLA route がない | target point proxy から始める |
| multi-camera | 実車カメラ構成未確定 | front camera mainline を先に作る |
| LiDAR fusion | 初期 mainline として維持 | camera + LiDAR のまま FP16 / TensorRT FP16 を優先 |
| 座標系 | CARLA と ROS で差異あり | `base_link` への変換を adapter に閉じ込める |
| Autoware trajectory | 依存が増える | Phase 2 では `nav_msgs/Path` 優先 |
| TensorRT 化 | 後段 | PyTorch runtime が通ってから検討 |
| MobileNetV3 化 | 新規 variant 扱い | ResNet34 FP16 baseline 後に fine-tuning / distillation 前提で検討 |

## 15. 参考リンク

- LEAD / TFv6 GitHub: https://github.com/kesai-labs/lead
- TFv6 checkpoint: https://huggingface.co/ln2697/tfv6
- Autoware `autoware_tensorrt_vad`: https://autowarefoundation.github.io/autoware_universe/latest/e2e/autoware_tensorrt_vad/
