# ShadowMode / E2E 現状まとめ

作成日: 2026-06-06

## 目的

この文書は AMaRanthus 側の `shadow_mode` / `e2e_transfuser` / GUI まわりについて、2026-06-06 時点の実装状態と次に検証すべきことをまとめる。

外向きのポートフォリオ説明は Helianthus の `docs/` に置き、この文書は実装者が topic contract と検証順序を追うための資料として扱う。

## 現在の到達点

### E2E 入力 contract

- E2E 用 pointcloud は既定で `/cloud_registered_body` を使う。
- `/cloud_registered` は GUI / virtual control / 通常の点群可視化向けとして残す。
- LEAD runtime は PointCloud2 から `rasterized_lidar` を生成し、以前の zero-only path から一歩進んだ。
- E2E raster path には TF 変換がないため、入力 frame は `body` または `base_link` など ego/body frame に限定する。
- `/shadow/e2e/status.lead_lidar_frame_contract` で frame が想定内か確認する。

### Route target contract

- `shadow_route_target` は `/shadow/route/target_point` に加え、選択した path を `/shadow/route/target_path` として publish する。
- source priority は `gui_route,image_lane,shadow_virtual` を基本とする。
- odometry 速度を使って lookahead を伸ばす speed-adaptive lookahead を持つ。
- E2E 側は `/shadow/route/target_path` から previous/current/next の3点を作り、LEAD の `target_point_previous/current/next` に渡す。
- 既定距離は previous=5m、current=15m、next=25m。

### Camera / overlay

- `e2e_path_overlay` は C++ node を通常 runtime の既定にする。
- LEAD 3-camera checkpoint 向けに `front_center_stitched` model input layout を追加した。
- 旧比較用には `e2e_model_input_layout:=resize` を使う。
- replay で CameraInfo が欠落する場合だけ、synthetic CameraInfo fallback を明示的に有効化できる。
- overlay は `/shadow/e2e/path` と `/shadow/perception/lane_path` を同時に描画できる。

### Camera lane detection

- classical OpenCV backend は HSV threshold、ROI、morphology、confidence、smoothing を launch / config で調整できる。
- debug mask / debug image publish を追加した。
- この node は route target support / debug 用であり、量産品質の lane model ではない。

### Phone route / GUI / logging

- phone location bridge は stale fix を fail-closed に扱い、古い current fix を route path に使わない。
- publish rate は 10Hz、route path 最大長は 400m。
- GUI rosbag preset と shadow bag regex に E2E 入力、E2E 出力、route target path、TF、`/cloud_registered_body` を含めた。
- `/shadow/e2e/path_raw_lead` を記録することで、LEAD 生出力と downstream path を比較できる。

## 重要 topic

| 種類 | Topic |
| --- | --- |
| Camera image | `/sensing/camera/camera0/image_rect_color` |
| Camera info | `/sensing/camera/camera0/camera_info` |
| E2E LiDAR raster input | `/cloud_registered_body` |
| GUI / virtual pointcloud | `/cloud_registered` |
| Odometry | `/Odometry` |
| GUI route path | `/shadow/route/gui_path` |
| E2E target point | `/shadow/route/target_point` |
| E2E target path | `/shadow/route/target_path` |
| Route target status | `/shadow/route/target_status` |
| E2E path | `/shadow/e2e/path` |
| LEAD raw path | `/shadow/e2e/path_raw_lead` |
| E2E health | `/shadow/e2e/status` |
| Overlay health | `/shadow/e2e/overlay_status` |
| GUI overlay | `/shadow/e2e/overlay_image/compressed` |

## 見るべき status fields

| Field | 意味 |
| --- | --- |
| `active_sensor_input_mode` | camera-only か camera+LiDAR 相当か |
| `lead_lidar_raster.source` | `pointcloud` か `zero` か |
| `lead_lidar_raster.nonzero_pixels` | raster に点群由来の占有があるか |
| `lead_lidar_raster.frame_id` | 入力 pointcloud の frame |
| `lead_lidar_frame_contract.frame_ok` | TF なしで使ってよい frame か |
| `lead_target_triplet.source` | path triplet が使われたか |
| `lead_target_triplet.frame_ok` | target path frame が想定内か |
| `missing_optional_inputs` | 欠けている入力 |
| `camera_info_source` | topic 由来か synthetic fallback か |
| `lead_forward_count` | model forward が進んでいるか |
| `input_age_sec` | 入力 freshness |

## 直近の検証計画

1. live shadow-only bag を1本取る。
2. `/shadow/e2e/status` が約10Hzで、`lead_forward_count` が止まらないことを確認する。
3. `lead_lidar_raster.source=pointcloud`、`nonzero_pixels > 0`、`frame_ok=true` を確認する。
4. `/shadow/route/target_status` が全区間 default fallback になっていないか確認する。
5. `front_center_stitched` vs `resize`、LiDAR raster on/off、target triplet on/off の A/B を行う。
6. それでも横方向 bias が残る場合だけ、output correction を研究用 option として評価する。

## 未完リスク

- LiDAR temporal history は ego-motion compensation が入るまで `1` を既定にする。
- `/cloud_registered_body` の frame contract が崩れると E2E 入力が誤る。
- replay は wiring 確認には有効だが、live 10Hz freshness の証拠としては不足する。
- camera lane は debug / target補助で、最終的には専用 model か実走データでの評価が必要。
