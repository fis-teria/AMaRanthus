# shadow_mode_localization_fusion

`shadow_mode_localization_fusion` combines continuous LiDAR odometry with low-rate
GNSS fixes for ShadowMode.

The node always republishes LiDAR odometry as `/shadow/fused/odometry`. When a
fresh `NavSatFix` is available from the phone or Spresense, it estimates a slow
XY correction and applies it to the LiDAR pose. Orientation and twist remain
LiDAR-derived so short-term motion stays smooth.

GNSS correction is speed-adaptive by default. At low speed it uses the normal
`correction_gain`; above `high_speed_threshold_mps` it blends down to
`high_speed_correction_gain` and a smaller `high_speed_max_correction_step_m` so
highway-speed odometry does not get large pose nudges that appear as ego-speed
spikes.

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

Useful highway-oriented tuning knobs:

```bash
ros2 launch shadow_mode_localization_fusion shadow_localization_fusion.launch.py \
  dynamic_correction_gain:=true \
  low_speed_threshold_mps:=3.0 \
  high_speed_threshold_mps:=20.0 \
  correction_gain:=0.08 \
  high_speed_correction_gain:=0.01 \
  high_speed_max_correction_step_m:=0.05
```

The E2E ShadowMode launch can use this output by setting:

```bash
use_localization_fusion:=true odom_topic:=/shadow/fused/odometry
```
