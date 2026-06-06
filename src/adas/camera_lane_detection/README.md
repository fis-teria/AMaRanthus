# camera_lane_detection

`camera_lane_detection` is the camera-side lane / road-shoulder perception adapter
for Shadow Mode route targets.

It is intentionally separate from the existing YOLO object detector. YOLO continues
to publish object detections and tracking boxes, while this package is for a
dedicated lane / road-edge mask.

Inputs:

- `/sensing/camera/camera0/image_rect_color` (`sensor_msgs/msg/Image`)
- `/sensing/camera/camera0/camera_info` (`sensor_msgs/msg/CameraInfo`)

Outputs:

- `/shadow/perception/lane_path` (`nav_msgs/msg/Path`)
- `/shadow/perception/lane_status` (`std_msgs/msg/String`, JSON)

The default backend is `opencv_classical`, a lightweight color/ROI based detector
that does not need a model file. It detects white/yellow markings inside a road
ROI, fits left/right lane edges, derives the current-lane center path, and smooths
the path over time. A low-confidence fit is reported in status and is not
published as a fake route path.

A dedicated ONNX semantic-segmentation model is still supported with
`backend:=opencv_onnx model_path:=...`. If the ONNX model is not configured or
cannot be loaded, the node publishes status only and does not publish a fake path.

Standalone launch:

```bash
ros2 launch camera_lane_detection camera_lane_detection.launch.py
```

Useful tuning / debug launch arguments:

```bash
ros2 launch camera_lane_detection camera_lane_detection.launch.py \
  publish_debug_images:=true \
  min_lane_confidence:=0.30 \
  smoothing_alpha:=0.35 \
  roi_top_ratio:=0.45
```

Debug outputs are disabled by default:

- `/shadow/perception/lane_mask` (`sensor_msgs/msg/Image`, `mono8`)
- `/shadow/perception/lane_debug_image` (`sensor_msgs/msg/Image`, `rgb8`)

`/shadow/perception/lane_status` reports `confidence`, left/right fitted band
counts, observed lane width, smoothing state, and the reason a path was withheld.

The E2E wrapper enables this package by default with `opencv_classical`. Set
`CAMERA_LANE_DETECTION=0` before launching E2E to disable it.
