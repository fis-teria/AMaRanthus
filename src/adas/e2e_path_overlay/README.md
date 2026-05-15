# e2e_path_overlay

`e2e_path_overlay` は、E2E TransFuser の `/shadow/e2e/path` をカメラ画像へ重ね描きして publish する ROS 2 パッケージです。

デフォルト入出力:

- image: `/sensing/camera/camera0/image_rect_color`
- camera info: `/sensing/camera/camera0/camera_info`
- path: `/shadow/e2e/path`
- overlay image: `/shadow/e2e/overlay_image`
- status: `/shadow/e2e/overlay_status`

起動例:

```bash
ros2 launch e2e_path_overlay e2e_path_overlay.launch.py
```

投影は forward-facing camera を想定し、`Path` の `x` 前方、`y` 左、`z` 上を、画像座標の右/下へ変換します。`use_tf_translation:=true` のときは `Path` frame から camera frame への TF translation を使い、見つからない場合は `camera_x_m/y_m/z_m` を fallback として使います。
