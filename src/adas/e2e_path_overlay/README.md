# e2e_path_overlay

`e2e_path_overlay` は、E2E TransFuser の `/shadow/e2e/path` をカメラ画像へ重ね描きして publish する ROS 2 パッケージです。

デフォルト入出力:

- image: `/sensing/camera/camera0/image_rect_color`
- camera info: `/sensing/camera/camera0/camera_info`
- path: `/shadow/e2e/path`
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

既定の実行ファイルは C++ 版の `e2e_path_overlay_node` です。旧 Python 実装で比較したい場合は
`executable:=e2e_path_overlay_node.py` を指定できます。

overlay 画像は表示負荷を下げるため、既定で長辺 `640px` へ縮小してから publish します。
変更する場合は `output_max_edge_px:=960` のように指定してください。`0` を指定すると入力解像度のまま出力します。

E2E/YOLO/カメラ白線検知向けの派生画像は、raw カメラ画像を一度 RGB8 に変換した結果から用途別に resize して publish します。
これにより `/sensing/camera/camera0/image_rect_color` の購読者を減らし、raw `1920x1280` YUV422 画像の fanout 負荷を抑えます。

投影は forward-facing camera を想定し、`Path` の `x` 前方、`y` 左、`z` 上を、画像座標の右/下へ変換します。`use_tf_translation:=true` のときは `Path` frame から camera frame への TF translation を使い、見つからない場合は `camera_x_m/y_m/z_m` を fallback として使います。
