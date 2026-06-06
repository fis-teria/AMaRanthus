# ChatGPT 相談用 ShadowMode / E2E ブリーフ

作成日: 2026-06-06

この文書は、ChatGPT へ貼り付けて ShadowMode / E2E planner 評価の研究・改善方針を相談するための入力フォーマットである。個人パス、秘密情報、実車の識別情報は含めない。

---

## ChatGPT への依頼

あなたは ROS 2、自動運転 ShadowMode 評価、camera-LiDAR E2E planning、replay / live data analysis に詳しい研究アドバイザーです。以下の現状を読んで、実装と研究をどう進めるべきか提案してください。

一般論ではなく、topic contract、status fields、live bag、A/B 実験、pass/fail criteria に基づいて具体的に答えてください。安全上、実車制御は行わず shadow-only を前提にしてください。

## プロジェクト概要

Helianthus / AMaRanthus は、実車制御を行わずに ADAS / E2E planner の判断を評価する ROS 2 ShadowMode 基盤です。

目的:

- camera、Livox LiDAR、FAST-LIO odometry、phone / GUI route を入力として使う。
- LEAD / TransFuser 系 E2E runtime を `/shadow/e2e/*` に接続する。
- GUI overlay と metrics で判断差分を可視化する。
- rosbag replay と live bag で再現可能に評価する。

非目標:

- アクチュエータ制御。
- 公道での自律走行。
- 量産 ADAS 相当の安全保証。

## 現在の構成

入力:

- `/sensing/camera/camera0/image_rect_color`
- `/sensing/camera/camera0/camera_info`
- `/cloud_registered_body`
- `/cloud_registered`
- `/Odometry`
- `/shadow/route/gui_path`
- `/shadow/route/target_point`
- `/shadow/route/target_path`
- `/tf`
- `/tf_static`

出力:

- `/shadow/e2e/path`
- `/shadow/e2e/path_raw_lead`
- `/shadow/e2e/status`
- `/shadow/e2e/overlay_status`
- `/shadow/e2e/overlay_image/compressed`
- `/shadow/route/target_status`

## 最近入れた改善

- PointCloud2 から LEAD 用 LiDAR raster を作るようにした。既定入力は `/cloud_registered_body`。
- LiDAR raster は TF 変換を持たないため、`body` / `base_link` など ego/body frame 前提。
- `/shadow/e2e/status` に `lead_lidar_raster` と `lead_lidar_frame_contract` を出す。
- `/shadow/route/target_path` から previous/current/next target triplet を作る。
- `/shadow/e2e/path_raw_lead` を publish し、生出力と補正後 path を比較できる。
- `front_center_stitched` と `resize` の camera preprocessing A/B ができる。
- replay 用に synthetic CameraInfo fallback を明示的に使える。
- GUI / rosbag preset に camera、LiDAR、TF、route、E2E status/path/raw path/model input を含めた。

## 既知の課題

- live 10Hz freshness は replay だけでは証明できない。
- LiDAR temporal history は ego-motion compensation 未実装のため、既定は1 frame。
- single front camera を LEAD 3-camera checkpoint に入れているため、domain gap が残る可能性がある。
- route target が default fallback になると、E2E path が道路方向と合わなく見える可能性がある。
- output correction を先に入れると、入力 contract の問題を隠すリスクがある。

## 次に取りたい live bag

必須:

- `/sensing/camera/camera0/image_rect_color`
- `/sensing/camera/camera0/camera_info`
- `/cloud_registered`
- `/cloud_registered_body`
- `/Odometry`
- `/tf`
- `/tf_static`
- `/shadow/route/gui_path`
- `/shadow/route/target_point`
- `/shadow/route/target_path`
- `/shadow/route/target_status`
- `/shadow/route/command`
- `/shadow/e2e/status`
- `/shadow/e2e/path`
- `/shadow/e2e/path_raw_lead`
- `/shadow/e2e/confidence`
- `/shadow/e2e/curvature`
- `/shadow/e2e/speed_target`
- `/shadow/e2e/steering_proxy`
- `/shadow/e2e/overlay_status`
- `/shadow/e2e/overlay_image/compressed`
- `/phone/location/status`
- `/vehicle/gps_status`

成功条件:

- `/shadow/e2e/status` と `/shadow/e2e/path` が 10Hz 近辺。
- `lead_forward_count` が連続して増える。
- `lead_lidar_raster.source=pointcloud`。
- `lead_lidar_raster.nonzero_pixels > 0`。
- `lead_lidar_frame_contract.frame_ok=true`。
- route target が全区間 default fallback ではない。
- target triplet の source / frame / 3点座標が status で追える。

## 相談したいこと

1. live bag 後に最初に行うべき A/B 実験を3つ選んでください。
2. LiDAR raster、target triplet、camera preprocessing が改善したかを判定する metrics を提案してください。
3. wrong-looking path が route target fallback 起因か、E2E model 起因かを切り分ける手順を提案してください。
4. multi-frame LiDAR history を試す前に必要な最小限の ego-motion compensation を提案してください。
5. output-side lateral correction を研究用に入れる場合の guardrail を提案してください。
6. ポートフォリオで誇張せず信頼される見せ方を提案してください。

## 期待する回答形式

1. Diagnosis summary
2. Prioritized experiment plan
3. Required topics / fields
4. Metrics and pass/fail criteria
5. Safety guardrails
6. Portfolio-ready explanation
