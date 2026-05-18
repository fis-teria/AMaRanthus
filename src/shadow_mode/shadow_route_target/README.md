# shadow_route_target

`shadow_route_target` converts route-like Shadow Mode paths into the
`/shadow/route/target_point` input consumed by `e2e_transfuser`.

It publishes:

- `/shadow/route/target_point` (`geometry_msgs/msg/PointStamped`)
- `/shadow/route/target_status` (`std_msgs/msg/String`, JSON)
- `/shadow/route/command` (`std_msgs/msg/String`, optional, defaults to `lane_follow`)

It subscribes to these path sources, in priority order by default:

- `/shadow/route/gui_path` (`nav_msgs/msg/Path`) for future GUI route integration.
- `/shadow/perception/lane_path` (`nav_msgs/msg/Path`) for future camera white-line
  and road-shoulder perception.
- `/shadow/virtual/path` (`nav_msgs/msg/Path`) from `shadow_mode_virtual_control`.

The GUI and camera lane topics are interface contracts for now. They should publish
a local route path in the vehicle frame, normally `base_link`. The current node does
not transform global `map` routes into `base_link`; a future GUI route bridge can add
TF-based conversion before publishing `/shadow/route/gui_path`.

For the current Shadow Mode path, `shadow_mode_virtual_control` builds
`/shadow/virtual/path` from `livox_lane_detection` scan output or PointCloud2 input.
`shadow_route_target` selects the first path pose near the configured lookahead
distance and republishes it as the E2E route target.

Standalone launch:

```bash
ros2 launch shadow_route_target shadow_route_target.launch.py
```
