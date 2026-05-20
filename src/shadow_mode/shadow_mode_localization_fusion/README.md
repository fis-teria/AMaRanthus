# shadow_mode_localization_fusion

`shadow_mode_localization_fusion` combines continuous LiDAR odometry with low-rate
GNSS fixes for ShadowMode.

The node always republishes LiDAR odometry as `/shadow/fused/odometry`. When a
fresh `NavSatFix` is available from the phone or Spresense, it estimates a slow
XY correction and applies it to the LiDAR pose. Orientation and twist remain
LiDAR-derived so short-term motion stays smooth.

## Inputs

- `/Odometry` (`nav_msgs/msg/Odometry`): FAST-LIO / LiDAR odometry.
- `/phone/gps/fix` (`sensor_msgs/msg/NavSatFix`): phone GNSS fix.
- `/spresense/gps/fix` (`sensor_msgs/msg/NavSatFix`): optional Spresense GNSS fix.

## Outputs

- `/shadow/fused/odometry` (`nav_msgs/msg/Odometry`)
- `/shadow/fused/path` (`nav_msgs/msg/Path`)
- `/shadow/fused/status` (`std_msgs/msg/String`, JSON)

## Launch

```bash
ros2 launch shadow_mode_localization_fusion shadow_localization_fusion.launch.py
```

The E2E ShadowMode launch can use this output by setting:

```bash
use_localization_fusion:=true odom_topic:=/shadow/fused/odometry
```
