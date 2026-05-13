# e2e_transfuser フェーズ別実装方針

作成日: 2026-05-13

## 1. 目的

`e2e_transfuser` は、LEAD / TransFuser V6 系モデルを Helianthus / AMaRanthus の ROS 2 環境へ接続し、実車制御に介入せず `/shadow/e2e/*` へ End-to-End 走行判断を publish するための ADAS パッケージである。

本ドキュメントは Phase 0 から Phase 4 までの実装方針、成果物、受け入れ基準をまとめる。詳細な topic 契約と軽量化方針は `doc/lead_transfuser_ros2_specification_ja.md` を正とする。

## 2. 前提

- パッケージ名は `e2e_transfuser` とする。
- 配置先は `amaranthus/src/adas/e2e_transfuser` とする。
- 初期実装は実車制御 topic を publish しない。
- camera + LiDAR + odometry を維持した E2E 評価を mainline とする。
- `/shadow/e2e/*` は shadow-mode 専用出力であり、車両制御 command ではない。
- LEAD 本体は vendor copy せず、外部 repo / checkpoint path を adapter から参照する。

## 3. Phase 0: 仕様固定

目的:

- LEAD / TransFuser ROS 2 化のパッケージ名、配置、topic 契約、軽量化方針を文書化する。

実装内容:

- `doc/lead_transfuser_ros2_specification_ja.md` を追加する。
- `doc/shadow_mode_specification_ja.md` に `e2e_transfuser` の拡張候補を追記する。
- 本ドキュメントで Phase 0 から Phase 4 の作業単位を固定する。

受け入れ基準:

- `e2e_transfuser` の配置先が `amaranthus/src/adas/e2e_transfuser` と明記されている。
- camera + LiDAR を維持した軽量化方針が明記されている。
- Phase ごとの成果物と検証方法が分離されている。

## 4. Phase 1: LEAD / checkpoint 検証導線

目的:

- 重い checkpoint をいきなり ROS node に組み込む前に、LEAD repo、checkpoint、Python runtime、モデル variant の状態を単体確認できるようにする。

実装内容:

- `e2e_transfuser_check_lead.py` を追加する。
- `LEAD_PROJECT_ROOT`、`model_path`、`model_variant`、runtime mode を検査する。
- checkpoint directory 内の `.pth`、`config.json`、`README.md` などを確認し、JSON summary を出力する。
- PyTorch / ONNX Runtime / TensorRT Python module の有無を optional dependency として報告する。

受け入れ基準:

- `ros2 run e2e_transfuser e2e_transfuser_check_lead.py --dry-run` 相当で環境診断ができる。
- checkpoint が無い場合でも失敗理由を JSON で説明し、例外 stacktrace だけで終わらない。
- 実 checkpoint download はこのフェーズの必須条件にしない。

## 5. Phase 2: ROS 2 wrapper MVP

目的:

- camera + LiDAR + odometry + target point の入力契約を ROS 2 node として固定し、mock runtime で `/shadow/e2e/*` 出力を publish できるようにする。

実装内容:

- `e2e_transfuser_node.py` を追加する。
- 入力 topic:
  - `/sensing/camera/camera0/image_rect_color`
  - `/sensing/camera/camera0/camera_info`
  - `/livox/lidar`
  - `/Odometry`
  - `/shadow/route/target_point`
- 出力 topic:
  - `/shadow/e2e/path`
  - `/shadow/e2e/steering_proxy`
  - `/shadow/e2e/curvature`
  - `/shadow/e2e/speed_target`
  - `/shadow/e2e/confidence`
  - `/shadow/e2e/status`
  - `/shadow/e2e/debug_markers`
- `runtime_mode=mock` では target point と odometry から単純な waypoint path を生成する。
- `runtime_mode=lead_python` はこのフェーズでは model path / dependency の状態を status に出し、未接続時も node を落とさない。

受け入れ基準:

- `colcon build --packages-select e2e_transfuser` が成功する。
- mock runtime で launch できる。
- 入力不足が `/shadow/e2e/status` の `missing_inputs` に出る。
- 入力が揃うと `/shadow/e2e/path` と proxy 値が publish される。

## 6. Phase 3: ShadowMode metrics 連携

目的:

- E2E 出力を既存 shadow-mode 評価軸へ接続し、driver proxy / virtual control / E2E の差分を比較できるようにする。

実装内容:

- `shadow_mode_e2e_metrics` を追加する。
- 入力 topic:
  - `/shadow/ego/speed`
  - `/shadow/ego/curvature`
  - `/shadow/virtual/steering_proxy`
  - `/shadow/virtual/curvature`
  - `/shadow/e2e/steering_proxy`
  - `/shadow/e2e/curvature`
  - `/shadow/e2e/confidence`
- 出力 topic:
  - `/shadow/metrics/e2e_steering_delta`
  - `/shadow/metrics/e2e_virtual_steering_delta`
  - `/shadow/metrics/e2e_curvature_delta`
  - `/shadow/metrics/e2e_intervention_score`
  - `/shadow/metrics/e2e_summary`
- `shadow_mode_bringup.launch.py` に `use_e2e_transfuser` と `use_e2e_metrics` を追加する。

受け入れ基準:

- `colcon build --packages-select e2e_transfuser shadow_mode_e2e_metrics shadow_mode_bringup` が成功する。
- bringup から E2E node と E2E metrics node を任意に起動できる。
- `/shadow/e2e/*` と既存 `/shadow/ego/*` / `/shadow/virtual/*` が揃うと E2E metrics が publish される。

## 7. Phase 4: 軽量化評価導線

目的:

- Z13 上で PyTorch FP32 / PyTorch FP16 / TensorRT FP16 / TensorRT INT8 の forward 評価を段階的に行える導線を作る。

実装内容:

- runtime mode に `lead_python`、`onnx`、`tensorrt` を明示的に残す。
- `precision_mode` を追加し、`fp32`、`fp16`、`int8` を設定可能にする。
- `disable_aux_heads`、`single_checkpoint`、`allow_int8` などの軽量化パラメータを追加する。
- `e2e_transfuser_benchmark.py` を追加し、指定 runtime / precision で latency と memory の JSON / CSV summary を出せるようにする。
- INT8 は `allow_int8=true` の明示指定がない限り実行しない。

受け入れ基準:

- `ros2 run e2e_transfuser e2e_transfuser_benchmark.py --runtime-mode mock --precision-mode fp16 --dry-run` が実行できる。
- PyTorch / ONNX Runtime / TensorRT が無い環境でも、どの依存が不足しているか summary に出る。
- FP16 と INT8 の比較方針が doc と runtime status の両方で表現される。

## 8. コミット方針

各 Phase の実装完了ごとに、その Phase で触ったファイルだけを stage して commit する。既存 worktree には他作業の未コミット変更があるため、無関係な GUI / setup / driver / submodule 差分は混ぜない。
