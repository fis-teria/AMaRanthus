# camera_lane_detection

`camera_lane_detection` is the camera-side lane / road-shoulder perception adapter
for Shadow Mode route targets.

It is intentionally separate from the existing YOLO object detector. YOLO continues
to publish object detections and tracking boxes, while this package is for a
dedicated semantic-segmentation model that produces a lane / road-edge mask.

Inputs:

- `/sensing/camera/camera0/image_rect_color` (`sensor_msgs/msg/Image`)
- `/sensing/camera/camera0/camera_info` (`sensor_msgs/msg/CameraInfo`)

Outputs:

- `/shadow/perception/lane_path` (`nav_msgs/msg/Path`)
- `/shadow/perception/lane_status` (`std_msgs/msg/String`, JSON)

The model interface currently supports ONNX semantic segmentation through OpenCV
DNN. Configure `model_path` to point at the dedicated lane model. If the model is
not configured or cannot be loaded, the node publishes status only and does not
publish a fake path. In that state it also avoids subscribing to the full-size
camera image so enabling the launch switch does not add raw-image delivery load
before a real model is installed.

Standalone launch:

```bash
ros2 launch camera_lane_detection camera_lane_detection.launch.py \
  model_path:=/home/graneple/Helianthus/amaranthus/Data/models/camera_lane/lane_segmentation.onnx
```

The E2E launch exposes this as `use_camera_lane_detection` and keeps it disabled
by default until a real model is installed.
