# shadow_mode_e2e_metrics

`shadow_mode_e2e_metrics` は、`/shadow/e2e/*` の E2E TransFuser 出力を、既存の `/shadow/ego/*` と `/shadow/virtual/*` と比較するための metrics ノードです。

## 起動

```bash
ros2 launch shadow_mode_e2e_metrics shadow_mode_e2e_metrics.launch.py
```

主な出力:

- `/shadow/metrics/e2e_steering_delta`
- `/shadow/metrics/e2e_virtual_steering_delta`
- `/shadow/metrics/e2e_curvature_delta`
- `/shadow/metrics/e2e_intervention_score`
- `/shadow/metrics/e2e_summary`
