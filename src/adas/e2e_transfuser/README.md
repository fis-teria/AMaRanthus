# e2e_transfuser

`e2e_transfuser` は、LEAD / TransFuser V6 系モデルを ROS 2 shadow-mode 評価へ接続するための ADAS パッケージです。

初期実装では実車制御 command を publish せず、camera + LiDAR + odometry + route proxy から `/shadow/e2e/*` に仮想 E2E 出力を publish します。

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

## Phase 4: 軽量化ベンチマーク導線

Z13 向けには、camera + LiDAR を維持したまま `PyTorch FP32 -> PyTorch FP16 -> TensorRT FP16 -> TensorRT INT8` の順に確認します。

```bash
ros2 run e2e_transfuser e2e_transfuser_benchmark.py \
  --runtime-mode mock \
  --precision-mode fp16 \
  --dry-run
```

INT8 は calibration data と経路差分評価が必要なため、`--allow-int8` を明示した場合だけ検討対象にします。
