# e2e_path_overlay

`e2e_path_overlay` は、E2E TransFuser の `/shadow/e2e/path` をカメラ画像へ重ね描きして publish する ROS 2 パッケージです。

デフォルト入出力:

- image: `/sensing/camera/camera0/image_rect_color`
- camera info: `/sensing/camera/camera0/camera_info`
- path: `/shadow/e2e/path`
- camera lane path: `/shadow/perception/lane_path`
- overlay image: `/shadow/e2e/overlay_image`
- compressed overlay image: `/shadow/e2e/overlay_image/compressed`
- E2E model input image: `/shadow/e2e/model_input_image` (`1152x384`, RGB8)
- YOLO input image: `/shadow/perception/yolo_input_image` (`960x640`, RGB8)
- camera lane input image: `/shadow/perception/lane_input_image` (`640x427`, RGB8)
- camera lane input camera info: `/shadow/perception/lane_input_camera_info`
- status: `/shadow/e2e/overlay_status`

起動例:

```bash
ros2 launch e2e_path_overlay e2e_path_overlay.launch.py
```

既定の実行ファイルは C++ 版の `e2e_path_overlay_node` です。旧 Python 実装は
overlay/status の比較用で、`/shadow/e2e/model_input_image` や YOLO/lane 派生画像は
publish しません。E2E runtime と組み合わせる通常経路では C++ 版を使ってください。

overlay 画像は表示負荷を下げるため、既定で長辺 `640px` へ縮小してから publish します。
変更する場合は `output_max_edge_px:=960` のように指定してください。`0` を指定すると入力解像度のまま出力します。

E2E/YOLO/カメラ白線検知向けの派生画像は、raw カメラ画像を一度 RGB8 に変換した結果から用途別に変換して publish します。
これにより `/sensing/camera/camera0/image_rect_color` の購読者を減らし、raw `1920x1280` YUV422 画像の fanout 負荷を抑えます。

`/shadow/perception/lane_path` が fresh な間は、E2E path と同じ forward-facing camera 投影で
camera lane path も overlay 画像へ描画します。既定では cyan の細線として描き、E2E path の
緑リボンとは別に見えるようにしています。`draw_lane_path:=false` で無効化できます。
`/shadow/e2e/overlay_status` には `lane_projected_count` と `lane_drawn_segments` が入ります。

リプレイで `camera_info` が欠ける場合は `synthesize_camera_info_when_missing:=true` を指定すると、
入力画像サイズから暫定 `CameraInfo` を合成します。`camera_info_source` と
`synthetic_camera_info_count` は `/shadow/e2e/overlay_status` に出ます。E2E path がまだ無い場合でも、
overlay node はカメラ確認用に path なしの overlay/compressed overlay を publish します。

E2E model input は既定で `model_input_layout:=front_center_stitched` です。
LEAD の 3-camera stitched 入力を想定し、`1152x384` を `384x384` の3スロットへ分けて、
前方カメラを中央スロット (`model_input_front_camera_slot:=1`) に center crop して配置します。
旧来の単純 resize へ戻して比較する場合は `model_input_layout:=resize` を指定してください。

投影は forward-facing camera を想定し、`Path` の `x` 前方、`y` 左、`z` 上を、画像座標の右/下へ変換します。`use_tf_translation:=true` のときは `Path` frame から camera frame への TF translation を使い、見つからない場合は `camera_x_m/y_m/z_m` を fallback として使います。
