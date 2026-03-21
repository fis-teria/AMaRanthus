# AMaRanthus Workspace Summary

このリポジトリに含まれる主要コンポーネントと、`src`配下のROSパッケージ一覧です。

## Top-Level Overview
- GUI: `gui/` (PyQt5 + PyQtWebEngine)
- ROS2 packages: `src/`
- Docker: `docker/`
- Utility scripts: ルートの `*.sh`, `rs-launch`, `rs-subscriber`

## ROS Package Summary

### src/drivers/ws_livox/src
- `livox_interfaces` (`src/drivers/ws_livox/src/livox_interfaces/package.xml`) - livox interface for livox ros2 driver
- `livox_ros2_driver` (`src/drivers/ws_livox/src/livox_ros2_driver/package.xml`) - livox ros2 driver
- `livox_sdk_vendor` (`src/drivers/ws_livox/src/livox_sdk_vendor/package.xml`) - (description未設定)

### src/drivers/realsense-ros
- `realsense2_camera` (`src/drivers/realsense-ros/realsense2_camera/package.xml`) - RealSense camera package allowing access to Intel D400 3D cameras
- `realsense2_camera_msgs` (`src/drivers/realsense-ros/realsense2_camera_msgs/package.xml`) - RealSense camera_msgs package containing realsense camera messages definitions
- `realsense2_description` (`src/drivers/realsense-ros/realsense2_description/package.xml`) - RealSense description package for Intel 3D D400 cameras

### src/img_proc/mediapipe_ros2_suite/src
- `mediapipe_ros2_interfaces` (`src/img_proc/mediapipe_ros2_suite/src/mediapipe_ros2_interfaces/package.xml`) - Interfaces (msgs) for Mediapipe ROS2 suite
- `mediapipe_ros2_node` (`src/img_proc/mediapipe_ros2_suite/src/mediapipe_ros2_node/package.xml`) - Assets (models/launch/rviz) for Mediapipe ROS2 suite
- `mediapipe_ros2_py` (`src/img_proc/mediapipe_ros2_suite/src/mediapipe_ros2_py/package.xml`) - Mediapipe ROS2 Python nodes (hand/pose/face)

### src/obstacle_app
- `obstacle_grid` (`src/obstacle_app/obstacle_grid/package.xml`) - Lightweight obstacle detection from pointcloud

### src/realsense_app
- `realsense_packages` (`src/realsense_app/realsense_packages/package.xml`) - TODO: Package description

### src/slam/navigation2
- `nav2_amcl` (`src/slam/navigation2/nav2_amcl/package.xml`) - (description未設定)
- `nav2_behavior_tree` (`src/slam/navigation2/nav2_behavior_tree/package.xml`) - TODO
- `nav2_behaviors` (`src/slam/navigation2/nav2_behaviors/package.xml`) - TODO
- `nav2_bringup` (`src/slam/navigation2/nav2_bringup/package.xml`) - Bringup scripts and configurations for the Nav2 stack
- `nav2_bt_navigator` (`src/slam/navigation2/nav2_bt_navigator/package.xml`) - TODO
- `nav2_collision_monitor` (`src/slam/navigation2/nav2_collision_monitor/package.xml`) - Collision Monitor
- `nav2_common` (`src/slam/navigation2/nav2_common/package.xml`) - Common support functionality used throughout the navigation 2 stack
- `nav2_constrained_smoother` (`src/slam/navigation2/nav2_constrained_smoother/package.xml`) - Ceres constrained smoother
- `nav2_controller` (`src/slam/navigation2/nav2_controller/package.xml`) - Controller action interface
- `nav2_core` (`src/slam/navigation2/nav2_core/package.xml`) - A set of headers for plugins core to the Nav2 stack
- `nav2_costmap_2d` (`src/slam/navigation2/nav2_costmap_2d/package.xml`) - (description未設定)
- `costmap_queue` (`src/slam/navigation2/nav2_dwb_controller/costmap_queue/package.xml`) - The costmap_queue package
- `dwb_core` (`src/slam/navigation2/nav2_dwb_controller/dwb_core/package.xml`) - TODO
- `dwb_critics` (`src/slam/navigation2/nav2_dwb_controller/dwb_critics/package.xml`) - The dwb_critics package
- `dwb_msgs` (`src/slam/navigation2/nav2_dwb_controller/dwb_msgs/package.xml`) - Message/Service definitions specifically for the dwb_core
- `dwb_plugins` (`src/slam/navigation2/nav2_dwb_controller/dwb_plugins/package.xml`) - (description未設定)
- `nav2_dwb_controller` (`src/slam/navigation2/nav2_dwb_controller/nav2_dwb_controller/package.xml`) - (description未設定)
- `nav_2d_msgs` (`src/slam/navigation2/nav2_dwb_controller/nav_2d_msgs/package.xml`) - Basic message types for two dimensional navigation, extending from geometry_msgs::Pose2D.
- `nav_2d_utils` (`src/slam/navigation2/nav2_dwb_controller/nav_2d_utils/package.xml`) - A handful of useful utility functions for nav_2d packages.
- `nav2_graceful_controller` (`src/slam/navigation2/nav2_graceful_controller/package.xml`) - Graceful motion controller
- `nav2_lifecycle_manager` (`src/slam/navigation2/nav2_lifecycle_manager/package.xml`) - A controller/manager for the lifecycle nodes of the Navigation 2 system
- `nav2_map_server` (`src/slam/navigation2/nav2_map_server/package.xml`) - (description未設定)
- `nav2_mppi_controller` (`src/slam/navigation2/nav2_mppi_controller/package.xml`) - nav2_mppi_controller
- `nav2_msgs` (`src/slam/navigation2/nav2_msgs/package.xml`) - Messages and service files for the Nav2 stack
- `nav2_navfn_planner` (`src/slam/navigation2/nav2_navfn_planner/package.xml`) - TODO
- `nav2_planner` (`src/slam/navigation2/nav2_planner/package.xml`) - TODO
- `nav2_regulated_pure_pursuit_controller` (`src/slam/navigation2/nav2_regulated_pure_pursuit_controller/package.xml`) - Regulated Pure Pursuit Controller
- `nav2_rotation_shim_controller` (`src/slam/navigation2/nav2_rotation_shim_controller/package.xml`) - Rotation Shim Controller
- `nav2_route` (`src/slam/navigation2/nav2_route/package.xml`) - A Route Graph planner to compliment the Planner Server
- `nav2_rviz_plugins` (`src/slam/navigation2/nav2_rviz_plugins/package.xml`) - Navigation 2 plugins for rviz
- `nav2_simple_commander` (`src/slam/navigation2/nav2_simple_commander/package.xml`) - An importable library for writing mobile robot applications in python3
- `nav2_smac_planner` (`src/slam/navigation2/nav2_smac_planner/package.xml`) - Smac global planning plugin: A*, Hybrid-A*, State Lattice
- `nav2_smoother` (`src/slam/navigation2/nav2_smoother/package.xml`) - Smoother action interface
- `nav2_system_tests` (`src/slam/navigation2/nav2_system_tests/package.xml`) - TODO
- `nav2_theta_star_planner` (`src/slam/navigation2/nav2_theta_star_planner/package.xml`) - Theta* Global Planning Plugin
- `nav2_util` (`src/slam/navigation2/nav2_util/package.xml`) - TODO
- `nav2_velocity_smoother` (`src/slam/navigation2/nav2_velocity_smoother/package.xml`) - Nav2's Output velocity smoother
- `nav2_voxel_grid` (`src/slam/navigation2/nav2_voxel_grid/package.xml`) - (description未設定)
- `nav2_waypoint_follower` (`src/slam/navigation2/nav2_waypoint_follower/package.xml`) - A waypoint follower navigation server
- `navigation2` (`src/slam/navigation2/navigation2/package.xml`) - (description未設定)

### src/slam/rtabmap_ros
- `rtabmap_conversions` (`src/slam/rtabmap_ros/rtabmap_conversions/package.xml`) - RTAB-Map's conversions package. This package can be used to convert rtabmap_msgs's msgs into RTAB-Map's library objects.
- `rtabmap_demos` (`src/slam/rtabmap_ros/rtabmap_demos/package.xml`) - RTAB-Map's demo launch files.
- `rtabmap_examples` (`src/slam/rtabmap_ros/rtabmap_examples/package.xml`) - RTAB-Map's example launch files.
- `rtabmap_launch` (`src/slam/rtabmap_ros/rtabmap_launch/package.xml`) - RTAB-Map's main launch files.
- `rtabmap_msgs` (`src/slam/rtabmap_ros/rtabmap_msgs/package.xml`) - RTAB-Map's msgs package.
- `rtabmap_odom` (`src/slam/rtabmap_ros/rtabmap_odom/package.xml`) - RTAB-Map's odometry package.
- `rtabmap_python` (`src/slam/rtabmap_ros/rtabmap_python/package.xml`) - RTAB-Map's python package.
- `rtabmap_ros` (`src/slam/rtabmap_ros/rtabmap_ros/package.xml`) - (description未設定)
- `rtabmap_rviz_plugins` (`src/slam/rtabmap_ros/rtabmap_rviz_plugins/package.xml`) - RTAB-Map's rviz plugins.
- `rtabmap_slam` (`src/slam/rtabmap_ros/rtabmap_slam/package.xml`) - RTAB-Map's SLAM package.
- `rtabmap_sync` (`src/slam/rtabmap_ros/rtabmap_sync/package.xml`) - RTAB-Map's synchronization package.
- `rtabmap_util` (`src/slam/rtabmap_ros/rtabmap_util/package.xml`) - RTAB-Map's various useful nodes and nodelets.
- `rtabmap_viz` (`src/slam/rtabmap_ros/rtabmap_viz/package.xml`) - RTAB-Map's visualization package.

## Notes
- 一部パッケージは `package.xml` の説明が未設定（`TODO` / `description未設定`）です。
- 実行・ビルド時はプロジェクトルールに従い、Docker内で `colcon build --symlink-install` を使用します。
