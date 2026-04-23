# shadow_mode_metrics

`shadow_mode_metrics` は、shadow-mode の ego 推定値と仮想制御値を同じ ROS 時刻軸で比較するための評価ノードです。

現時点では実 CAN / OBD のドライバ操作量入力がないため、`/shadow/ego/curvature` から `driver_steering_proxy = atan(wheelbase * ego_curvature)` を推定し、`/shadow/virtual/steering_proxy` との差分を driver-vs-virtual の最小比較値として扱います。

## 入力

- `/shadow/ego/speed`
- `/shadow/ego/curvature`
- `/shadow/virtual/steering_proxy`
- `/shadow/virtual/curvature`
- `/shadow/virtual/warning_score`

## 出力

- `/shadow/metrics/driver_steering_proxy`: Ego 曲率由来のドライバ操舵代理値 `[rad]`
- `/shadow/metrics/steering_delta`: `virtual_steering - driver_steering_proxy` `[rad]`
- `/shadow/metrics/curvature_delta`: `virtual_curvature - ego_curvature` `[1/m]`
- `/shadow/metrics/intervention_score`: 操舵差分、曲率差分、仮想 warning を合成した `0.0` から `1.0` の評価値
- `/shadow/metrics/control_delta`: stamped vector。`x=steering_delta`, `y=curvature_delta`, `z=intervention_score`
- `/shadow/metrics/summary`: JSON 形式の同期メトリクス

## 起動例

```bash
ros2 launch shadow_mode_metrics shadow_mode_metrics.launch.py
```

CSV ログを有効にする場合は、bringup 側またはパラメータファイルで `enable_csv_logging:=true` 相当の設定を使います。
