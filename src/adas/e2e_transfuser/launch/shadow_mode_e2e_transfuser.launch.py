import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import EnvironmentVariable, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    source_dir = os.path.realpath(__file__)
    for _ in range(4):
        source_dir = os.path.dirname(source_dir)
    amaranthus_dir = os.path.dirname(source_dir)
    yolo_cuda_venv_site = os.path.join(
        amaranthus_dir,
        "Data",
        "venvs",
        "yolo_ros_cuda",
        "lib",
        "python3.10",
        "site-packages",
    )
    yolo_cuda_torch_lib = os.path.join(yolo_cuda_venv_site, "torch", "lib")
    yolo_model_path = os.path.join(amaranthus_dir, "Data", "models", "yolo", "yolo11n.pt")
    lead_project_root_path = os.path.join(amaranthus_dir, "Data", "src", "lead")
    lead_model_path = os.path.join(amaranthus_dir, "Data", "models", "tfv6", "tfv6_resnet34")

    e2e_share = FindPackageShare("e2e_transfuser")
    shadow_bringup_share = FindPackageShare("shadow_mode_bringup")
    e2e_metrics_share = FindPackageShare("shadow_mode_e2e_metrics")
    camera_lidar_bringup_share = FindPackageShare("camera_lidar_bringup")
    e2e_path_overlay_share = FindPackageShare("e2e_path_overlay")
    camera_lane_detection_share = FindPackageShare("camera_lane_detection")
    livox_lane_detection_share = FindPackageShare("livox_lane_detection")
    adas_description_share = FindPackageShare("adas_description")
    fast_lio_share = FindPackageShare("fast_lio")

    use_camera_lidar_bringup = LaunchConfiguration("use_camera_lidar_bringup")
    use_adas_description = LaunchConfiguration("use_adas_description")
    use_fast_lio = LaunchConfiguration("use_fast_lio")
    use_shadow_mode_bringup = LaunchConfiguration("use_shadow_mode_bringup")
    use_e2e_transfuser = LaunchConfiguration("use_e2e_transfuser")
    use_e2e_metrics = LaunchConfiguration("use_e2e_metrics")
    use_e2e_path_overlay = LaunchConfiguration("use_e2e_path_overlay")
    use_livox_lane_detection = LaunchConfiguration("use_livox_lane_detection")
    use_camera_lane_detection = LaunchConfiguration("use_camera_lane_detection")
    use_route_target = LaunchConfiguration("use_route_target")

    e2e_param_file = LaunchConfiguration("e2e_param_file")
    e2e_metrics_param_file = LaunchConfiguration("e2e_metrics_param_file")
    e2e_path_overlay_param_file = LaunchConfiguration("e2e_path_overlay_param_file")

    shadow_mode = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution(
                [shadow_bringup_share, "launch", "shadow_mode_bringup.launch.py"]
            )
        ),
        launch_arguments={
            "use_adas_bringup": LaunchConfiguration("use_adas_bringup"),
            # FAST-LIO is launched directly from this E2E wrapper so ADAS bringup can stay off.
            "use_fast_lio": "false",
            "virtual_input_mode": LaunchConfiguration("virtual_input_mode"),
            "lane_detection_scan_topic": LaunchConfiguration("lane_detection_scan_topic"),
            "virtual_pointcloud_topic": LaunchConfiguration("pointcloud_topic"),
            "pointcloud_topic": LaunchConfiguration("pointcloud_topic"),
            "odom_topic": LaunchConfiguration("odom_topic"),
            "use_localization_fusion": LaunchConfiguration("use_localization_fusion"),
            "localization_lidar_odom_topic": LaunchConfiguration("localization_lidar_odom_topic"),
            "phone_fix_topic": LaunchConfiguration("phone_fix_topic"),
            "spresense_fix_topic": LaunchConfiguration("spresense_fix_topic"),
            "fused_odom_topic": LaunchConfiguration("fused_odom_topic"),
            "fused_path_topic": LaunchConfiguration("fused_path_topic"),
            "fused_status_topic": LaunchConfiguration("fused_status_topic"),
            "localization_fix_timeout_sec": LaunchConfiguration("localization_fix_timeout_sec"),
            "localization_max_fix_accuracy_m": LaunchConfiguration(
                "localization_max_fix_accuracy_m"
            ),
            "localization_correction_gain": LaunchConfiguration(
                "localization_correction_gain"
            ),
            "use_route_target": use_route_target,
            "use_phone_location_bridge": LaunchConfiguration("use_phone_location_bridge"),
            "route_target_output_topic": LaunchConfiguration("target_point_topic"),
            "route_command_topic": LaunchConfiguration("route_command_topic"),
            "route_target_publish_rate_hz": LaunchConfiguration("route_target_publish_rate_hz"),
            "route_target_input_timeout_sec": LaunchConfiguration("input_timeout_sec"),
            "route_target_lookahead_distance_m": LaunchConfiguration(
                "route_target_lookahead_distance_m"
            ),
            "route_target_source_priority": LaunchConfiguration(
                "route_target_source_priority"
            ),
            "route_target_publish_default_when_missing": LaunchConfiguration(
                "route_target_publish_default_when_missing"
            ),
            "gui_route_path_topic": LaunchConfiguration("gui_route_path_topic"),
            "image_lane_path_topic": LaunchConfiguration("image_lane_path_topic"),
            "shadow_virtual_path_topic": LaunchConfiguration("shadow_virtual_path_topic"),
            "phone_bridge_server_host": LaunchConfiguration("phone_bridge_server_host"),
            "phone_bridge_server_port": LaunchConfiguration("phone_bridge_server_port"),
            "phone_bridge_use_https": LaunchConfiguration("phone_bridge_use_https"),
            "phone_bridge_tls_cert_file": LaunchConfiguration("phone_bridge_tls_cert_file"),
            "phone_bridge_tls_key_file": LaunchConfiguration("phone_bridge_tls_key_file"),
            "phone_bridge_osrm_service_url": LaunchConfiguration("phone_bridge_osrm_service_url"),
            "phone_bridge_fix_topic": LaunchConfiguration("phone_bridge_fix_topic"),
            "phone_bridge_goal_topic": LaunchConfiguration("phone_bridge_goal_topic"),
            "phone_bridge_gps_status_topic": LaunchConfiguration("phone_bridge_gps_status_topic"),
            "phone_bridge_status_topic": LaunchConfiguration("phone_bridge_status_topic"),
            "phone_bridge_route_command": LaunchConfiguration("phone_bridge_route_command"),
            "phone_bridge_auto_reroute_enabled": LaunchConfiguration(
                "phone_bridge_auto_reroute_enabled"
            ),
            "phone_bridge_off_route_threshold_m": LaunchConfiguration(
                "phone_bridge_off_route_threshold_m"
            ),
            "phone_bridge_off_route_hold_sec": LaunchConfiguration(
                "phone_bridge_off_route_hold_sec"
            ),
            "phone_bridge_reroute_cooldown_sec": LaunchConfiguration(
                "phone_bridge_reroute_cooldown_sec"
            ),
            "record_shadow_bag": LaunchConfiguration("record_shadow_bag"),
            "bag_record_regex": LaunchConfiguration("bag_record_regex"),
            "metrics_csv_logging": LaunchConfiguration("metrics_csv_logging"),
        }.items(),
        condition=IfCondition(use_shadow_mode_bringup),
    )

    adas_description = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution(
                [adas_description_share, "launch", "adas_description.launch.py"]
            )
        ),
        launch_arguments={
            "robot_description_path": LaunchConfiguration("robot_description_path"),
            "use_sim_time": LaunchConfiguration("use_sim_time"),
        }.items(),
        condition=IfCondition(use_adas_description),
    )

    fast_lio = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([fast_lio_share, "launch", "mapping.launch.py"])
        ),
        launch_arguments={
            "use_sim_time": LaunchConfiguration("use_sim_time"),
            "config_path": LaunchConfiguration("fast_lio_config_path"),
            "config_file": LaunchConfiguration("fast_lio_config_file"),
            "rviz": LaunchConfiguration("use_fast_lio_rviz"),
            "rviz_cfg": LaunchConfiguration("fast_lio_rviz_cfg"),
        }.items(),
        condition=IfCondition(use_fast_lio),
    )

    camera_lidar_bringup = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution(
                [
                    camera_lidar_bringup_share,
                    "launch",
                    "camera_lidar_bringup.launch.py",
                ]
            )
        ),
        launch_arguments={
            "use_v4l2_camera": LaunchConfiguration("use_v4l2_camera"),
            "use_livox_driver": LaunchConfiguration("use_livox_driver"),
            "use_livox_rviz": LaunchConfiguration("use_livox_rviz"),
            "use_yolo": LaunchConfiguration("use_yolo"),
            "v4l2_image_topic": LaunchConfiguration("v4l2_image_topic"),
            "v4l2_camera_name": LaunchConfiguration("v4l2_camera_name"),
            "v4l2_camera_namespace": LaunchConfiguration("v4l2_camera_namespace"),
            "v4l2_camera_param_path": LaunchConfiguration("v4l2_camera_param_path"),
            "rate_diagnostics_param_path": LaunchConfiguration(
                "rate_diagnostics_param_path"
            ),
            "camera_info_url": LaunchConfiguration("camera_info_url"),
            "use_sensor_data_qos": LaunchConfiguration("use_sensor_data_qos"),
            "camera_publish_rate": LaunchConfiguration("camera_publish_rate"),
            "camera_time_per_frame": LaunchConfiguration("camera_time_per_frame"),
            "camera_output_encoding": LaunchConfiguration("camera_output_encoding"),
            "use_v4l2_buffer_timestamps": LaunchConfiguration("use_v4l2_buffer_timestamps"),
            "v4l2_video_device": LaunchConfiguration("v4l2_video_device"),
            "use_v4l2_preflight": LaunchConfiguration("use_v4l2_preflight"),
            "v4l2_expected_device_name": LaunchConfiguration("v4l2_expected_device_name"),
            "v4l2_strict_device_check": LaunchConfiguration("v4l2_strict_device_check"),
            "camera_hardware_id": LaunchConfiguration("camera_hardware_id"),
            "yolo_model": LaunchConfiguration("yolo_model"),
            "yolo_device": LaunchConfiguration("yolo_device"),
            "yolo_enable": LaunchConfiguration("yolo_enable"),
            "yolo_threshold": LaunchConfiguration("yolo_threshold"),
            "yolo_iou": LaunchConfiguration("yolo_iou"),
            "yolo_encoding": LaunchConfiguration("yolo_encoding"),
            "yolo_tracker": LaunchConfiguration("yolo_tracker"),
            "yolo_imgsz_height": LaunchConfiguration("yolo_imgsz_height"),
            "yolo_imgsz_width": LaunchConfiguration("yolo_imgsz_width"),
            "yolo_half": LaunchConfiguration("yolo_half"),
            "yolo_fuse_model": LaunchConfiguration("yolo_fuse_model"),
            "yolo_max_det": LaunchConfiguration("yolo_max_det"),
            "yolo_input_image_topic": LaunchConfiguration("yolo_input_image_topic"),
            "yolo_image_reliability": LaunchConfiguration("yolo_image_reliability"),
            "yolo_namespace": LaunchConfiguration("yolo_namespace"),
            "yolo_use_tracking": LaunchConfiguration("yolo_use_tracking"),
            "yolo_use_debug": LaunchConfiguration("yolo_use_debug"),
            "yolo_python_site": LaunchConfiguration("yolo_python_site"),
            "yolo_torch_lib": LaunchConfiguration("yolo_torch_lib"),
        }.items(),
        condition=IfCondition(use_camera_lidar_bringup),
    )

    livox_lane_detection = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution(
                [
                    livox_lane_detection_share,
                    "launch",
                    "livox_lane_detection_live.launch.py",
                ]
            )
        ),
        launch_arguments={
            "pointcloud_topic": LaunchConfiguration("pointcloud_topic"),
            "colored_cloud_topic": LaunchConfiguration(
                "lane_detection_colored_cloud_topic"
            ),
            "lane_scan_topic": LaunchConfiguration("lane_detection_scan_topic"),
            "objects_topic": LaunchConfiguration("lane_detection_objects_topic"),
            "model_path": LaunchConfiguration("lane_detection_model_path"),
            "output_frame": LaunchConfiguration("lane_detection_output_frame"),
            "torch_lib_path": LaunchConfiguration("lane_detection_torch_lib_path"),
            "publish_colored_cloud": LaunchConfiguration(
                "lane_detection_publish_colored_cloud"
            ),
            "publish_lane_scan": LaunchConfiguration("lane_detection_publish_lane_scan"),
            "publish_obstacles": LaunchConfiguration("lane_detection_publish_obstacles"),
            "publish_timing_log": LaunchConfiguration("lane_detection_publish_timing_log"),
            "timing_log_interval_sec": LaunchConfiguration(
                "lane_detection_timing_log_interval_sec"
            ),
            "max_process_rate_hz": LaunchConfiguration("lane_detection_max_process_rate_hz"),
            "device": LaunchConfiguration("lane_detection_device"),
            "launch_livox_driver": "false",
        }.items(),
        condition=IfCondition(use_livox_lane_detection),
    )

    camera_lane_detection = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution(
                [
                    camera_lane_detection_share,
                    "launch",
                    "camera_lane_detection.launch.py",
                ]
            )
        ),
        launch_arguments={
            "enabled": LaunchConfiguration("camera_lane_detection_enabled"),
            "backend": LaunchConfiguration("camera_lane_detection_backend"),
            "model_path": LaunchConfiguration("camera_lane_detection_model_path"),
            "camera_lane_detection_image_topic": LaunchConfiguration(
                "camera_lane_detection_image_topic"
            ),
            "camera_lane_detection_camera_info_topic": LaunchConfiguration(
                "camera_lane_detection_camera_info_topic"
            ),
            "output_path_topic": LaunchConfiguration("image_lane_path_topic"),
            "status_topic": LaunchConfiguration("camera_lane_detection_status_topic"),
            "output_frame": LaunchConfiguration("camera_lane_detection_output_frame"),
            "max_process_rate_hz": LaunchConfiguration("camera_lane_detection_max_process_rate_hz"),
            "input_width": LaunchConfiguration("camera_lane_detection_input_width"),
            "input_height": LaunchConfiguration("camera_lane_detection_input_height"),
        }.items(),
        condition=IfCondition(use_camera_lane_detection),
    )

    e2e_transfuser = Node(
        package="e2e_transfuser",
        executable="e2e_transfuser_node.py",
        name="e2e_transfuser",
        output="screen",
        additional_env={
            "PYTHONPATH": [
                LaunchConfiguration("lead_python_site"),
                ":",
                EnvironmentVariable("PYTHONPATH", default_value=""),
            ],
            "LD_LIBRARY_PATH": [
                LaunchConfiguration("lead_torch_lib"),
                ":",
                EnvironmentVariable("LD_LIBRARY_PATH", default_value=""),
            ],
        },
        parameters=[
            e2e_param_file,
            {
                "runtime_mode": LaunchConfiguration("e2e_runtime_mode"),
                "precision_mode": LaunchConfiguration("e2e_precision_mode"),
                "model_variant": LaunchConfiguration("e2e_model_variant"),
                "model_path": LaunchConfiguration("e2e_model_path"),
                "lead_project_root": LaunchConfiguration("lead_project_root"),
                "lead_python_site": LaunchConfiguration("lead_python_site"),
                "lead_torch_lib": LaunchConfiguration("lead_torch_lib"),
                "runtime_device": LaunchConfiguration("e2e_runtime_device"),
                "input_preprocess_backend": LaunchConfiguration("e2e_input_preprocess_backend"),
                "lead_strict_weight_load": ParameterValue(
                    LaunchConfiguration("lead_strict_weight_load"), value_type=bool
                ),
                "lead_probe_on_startup": ParameterValue(
                    LaunchConfiguration("lead_probe_on_startup"), value_type=bool
                ),
                "lead_force_timm_pretrained_off": ParameterValue(
                    LaunchConfiguration("lead_force_timm_pretrained_off"), value_type=bool
                ),
                "disable_aux_heads": ParameterValue(
                    LaunchConfiguration("disable_aux_heads"), value_type=bool
                ),
                "single_checkpoint": ParameterValue(
                    LaunchConfiguration("single_checkpoint"), value_type=bool
                ),
                "allow_int8": ParameterValue(
                    LaunchConfiguration("allow_int8"), value_type=bool
                ),
                "image_topic": LaunchConfiguration("e2e_input_image_topic"),
                "disable_image_fallback_topics": ParameterValue(
                    LaunchConfiguration("e2e_disable_image_fallback_topics"),
                    value_type=bool,
                ),
                "camera_info_topic": LaunchConfiguration("camera_info_topic"),
                "pointcloud_topic": LaunchConfiguration("pointcloud_topic"),
                "sensor_input_mode": LaunchConfiguration("e2e_sensor_input_mode"),
                "odom_topic": LaunchConfiguration("odom_topic"),
                "target_point_topic": LaunchConfiguration("target_point_topic"),
                "require_target_point": ParameterValue(
                    LaunchConfiguration("require_target_point"), value_type=bool
                ),
                "publish_rate_hz": ParameterValue(
                    LaunchConfiguration("e2e_publish_rate_hz"), value_type=float
                ),
                "input_timeout_sec": ParameterValue(
                    LaunchConfiguration("input_timeout_sec"), value_type=float
                ),
                "camera_only_confidence_scale": ParameterValue(
                    LaunchConfiguration("e2e_camera_only_confidence_scale"), value_type=float
                ),
            },
        ],
        condition=IfCondition(use_e2e_transfuser),
    )

    e2e_metrics = Node(
        package="shadow_mode_e2e_metrics",
        executable="shadow_mode_e2e_metrics_node.py",
        name="shadow_mode_e2e_metrics",
        output="screen",
        parameters=[
            e2e_metrics_param_file,
            {
                "publish_rate_hz": ParameterValue(
                    LaunchConfiguration("e2e_metrics_publish_rate_hz"), value_type=float
                ),
                "input_timeout_sec": ParameterValue(
                    LaunchConfiguration("input_timeout_sec"), value_type=float
                ),
            },
        ],
        condition=IfCondition(use_e2e_metrics),
    )

    e2e_path_overlay = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution(
                [
                    e2e_path_overlay_share,
                    "launch",
                    "e2e_path_overlay.launch.py",
                ]
            )
        ),
        launch_arguments={
            "param_file": e2e_path_overlay_param_file,
            "image_topic": LaunchConfiguration("e2e_overlay_input_image_topic"),
            "camera_info_topic": LaunchConfiguration("camera_info_topic"),
            "path_topic": LaunchConfiguration("e2e_path_topic"),
            "yolo_detections_topic": LaunchConfiguration("yolo_detections_topic"),
            "output_image_topic": LaunchConfiguration("e2e_overlay_image_topic"),
            "output_compressed_image_topic": LaunchConfiguration(
                "e2e_overlay_compressed_image_topic"
            ),
            "output_compressed_jpeg_quality": LaunchConfiguration(
                "e2e_overlay_compressed_jpeg_quality"
            ),
            "model_input_image_topic": LaunchConfiguration("e2e_model_input_image_topic"),
            "yolo_input_image_topic": LaunchConfiguration("e2e_yolo_input_image_topic"),
            "lane_input_image_topic": LaunchConfiguration("e2e_lane_input_image_topic"),
            "lane_input_camera_info_topic": LaunchConfiguration(
                "e2e_lane_input_camera_info_topic"
            ),
            "use_tf_translation": LaunchConfiguration("e2e_overlay_use_tf_translation"),
            "output_max_edge_px": LaunchConfiguration("e2e_overlay_output_max_edge_px"),
            "process_rate_hz": LaunchConfiguration("e2e_overlay_process_rate_hz"),
            "stale_image_timeout_sec": LaunchConfiguration(
                "e2e_overlay_stale_image_timeout_sec"
            ),
            "model_input_width_px": LaunchConfiguration("e2e_model_input_width_px"),
            "model_input_height_px": LaunchConfiguration("e2e_model_input_height_px"),
            "yolo_input_width_px": LaunchConfiguration("e2e_yolo_input_width_px"),
            "yolo_input_height_px": LaunchConfiguration("e2e_yolo_input_height_px"),
            "lane_input_width_px": LaunchConfiguration("e2e_lane_input_width_px"),
            "lane_input_height_px": LaunchConfiguration("e2e_lane_input_height_px"),
        }.items(),
        condition=IfCondition(use_e2e_path_overlay),
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("use_camera_lidar_bringup", default_value="true"),
            DeclareLaunchArgument("use_shadow_mode_bringup", default_value="true"),
            DeclareLaunchArgument("use_e2e_transfuser", default_value="true"),
            DeclareLaunchArgument("use_e2e_metrics", default_value="true"),
            DeclareLaunchArgument("use_e2e_path_overlay", default_value="true"),
            DeclareLaunchArgument("use_v4l2_camera", default_value="true"),
            DeclareLaunchArgument("use_adas_description", default_value="true"),
            DeclareLaunchArgument("use_fast_lio", default_value="true"),
            DeclareLaunchArgument("use_sim_time", default_value="false"),
            DeclareLaunchArgument("use_livox_driver", default_value="true"),
            DeclareLaunchArgument("use_livox_rviz", default_value="false"),
            DeclareLaunchArgument("use_fast_lio_rviz", default_value="false"),
            DeclareLaunchArgument("use_yolo", default_value="true"),
            DeclareLaunchArgument("use_livox_lane_detection", default_value="false"),
            DeclareLaunchArgument("use_camera_lane_detection", default_value="false"),
            DeclareLaunchArgument("use_adas_bringup", default_value="false"),
            DeclareLaunchArgument("use_localization_fusion", default_value="true"),
            DeclareLaunchArgument("use_route_target", default_value="true"),
            DeclareLaunchArgument("use_phone_location_bridge", default_value="false"),
            DeclareLaunchArgument("virtual_input_mode", default_value="pointcloud"),
            DeclareLaunchArgument(
                "robot_description_path",
                default_value=PathJoinSubstitution(
                    [adas_description_share, "urdf", "adas_livox.urdf"]
                ),
            ),
            DeclareLaunchArgument(
                "fast_lio_config_path",
                default_value=PathJoinSubstitution([fast_lio_share, "config"]),
            ),
            DeclareLaunchArgument("fast_lio_config_file", default_value="mid360.yaml"),
            DeclareLaunchArgument(
                "fast_lio_rviz_cfg",
                default_value=PathJoinSubstitution([fast_lio_share, "rviz", "fastlio.rviz"]),
            ),
            DeclareLaunchArgument(
                "lane_detection_scan_topic",
                default_value="/livox/lane_detection/scan",
            ),
            DeclareLaunchArgument(
                "lane_detection_colored_cloud_topic",
                default_value="/livox/lane_detection/points_with_class",
            ),
            DeclareLaunchArgument(
                "lane_detection_objects_topic",
                default_value="/livox/lane_detection/objects",
            ),
            DeclareLaunchArgument("lane_detection_publish_colored_cloud", default_value="false"),
            DeclareLaunchArgument("lane_detection_publish_lane_scan", default_value="true"),
            DeclareLaunchArgument("lane_detection_publish_obstacles", default_value="false"),
            DeclareLaunchArgument("lane_detection_publish_timing_log", default_value="true"),
            DeclareLaunchArgument("lane_detection_timing_log_interval_sec", default_value="2.0"),
            DeclareLaunchArgument("lane_detection_max_process_rate_hz", default_value="5.0"),
            DeclareLaunchArgument("lane_detection_device", default_value="cuda:0"),
            DeclareLaunchArgument(
                "lane_detection_model_path",
                default_value=PathJoinSubstitution(
                    [
                        livox_lane_detection_share,
                        "model",
                        "livox_lane_det.ts",
                    ]
                ),
            ),
            DeclareLaunchArgument("lane_detection_output_frame", default_value=""),
            DeclareLaunchArgument(
                "lane_detection_torch_lib_path",
                default_value="/opt/libtorch/lib",
                description=(
                    "libtorch runtime library directory for livox_lane_detection. "
                    "CUDA builds can pass a colon-separated torch/nvjitlink library path."
                ),
            ),
            DeclareLaunchArgument("pointcloud_topic", default_value="/cloud_registered"),
            DeclareLaunchArgument("localization_lidar_odom_topic", default_value="/Odometry"),
            DeclareLaunchArgument("odom_topic", default_value="/shadow/fused/odometry"),
            DeclareLaunchArgument("phone_fix_topic", default_value="/phone/gps/fix"),
            DeclareLaunchArgument("spresense_fix_topic", default_value="/spresense/gps/fix"),
            DeclareLaunchArgument("fused_odom_topic", default_value="/shadow/fused/odometry"),
            DeclareLaunchArgument("fused_path_topic", default_value="/shadow/fused/path"),
            DeclareLaunchArgument("fused_status_topic", default_value="/shadow/fused/status"),
            DeclareLaunchArgument("localization_fix_timeout_sec", default_value="3.0"),
            DeclareLaunchArgument("localization_max_fix_accuracy_m", default_value="25.0"),
            DeclareLaunchArgument("localization_correction_gain", default_value="0.08"),
            DeclareLaunchArgument("image_topic", default_value="/sensing/camera/camera0/image_rect_color"),
            DeclareLaunchArgument("camera_info_topic", default_value="/sensing/camera/camera0/camera_info"),
            DeclareLaunchArgument("v4l2_image_topic", default_value="image_rect_color"),
            DeclareLaunchArgument("v4l2_camera_name", default_value="camera0"),
            DeclareLaunchArgument("v4l2_camera_namespace", default_value="/sensing/camera"),
            DeclareLaunchArgument(
                "v4l2_camera_param_path",
                default_value=PathJoinSubstitution(
                    [
                        camera_lidar_bringup_share,
                        "config",
                        "tier4_c2_v4l2_camera.param.yaml",
                    ]
                ),
            ),
            DeclareLaunchArgument(
                "rate_diagnostics_param_path",
                default_value=PathJoinSubstitution(
                    [
                        camera_lidar_bringup_share,
                        "config",
                        "rate_diagnostics.param.yaml",
                    ]
                ),
            ),
            DeclareLaunchArgument("camera_info_url", default_value=""),
            DeclareLaunchArgument("use_sensor_data_qos", default_value="true"),
            DeclareLaunchArgument("camera_publish_rate", default_value="10.0"),
            DeclareLaunchArgument("camera_time_per_frame", default_value="auto"),
            DeclareLaunchArgument(
                "camera_output_encoding",
                default_value="rgb8",
                description="V4L2 camera output encoding; use yuv422 to pass UYVY through.",
            ),
            DeclareLaunchArgument("use_v4l2_buffer_timestamps", default_value="false"),
            DeclareLaunchArgument(
                "v4l2_video_device",
                default_value="",
                description=(
                    "Optional stable V4L2 device path forwarded to camera_lidar_bringup. "
                    "Prefer /dev/v4l/by-id or /dev/v4l/by-path over /dev/videoN."
                ),
            ),
            DeclareLaunchArgument("use_v4l2_preflight", default_value="true"),
            DeclareLaunchArgument(
                "v4l2_expected_device_name",
                default_value="TIER IV,GMSL2-USB3.0 Conversion Kit",
                description="Warn when the selected camera does not look like the expected unit.",
            ),
            DeclareLaunchArgument("v4l2_strict_device_check", default_value="false"),
            DeclareLaunchArgument(
                "camera_hardware_id",
                default_value="tier4_automotive_hdr_camera_c2",
            ),
            DeclareLaunchArgument("yolo_model", default_value=yolo_model_path),
            DeclareLaunchArgument("yolo_device", default_value="cuda:0"),
            DeclareLaunchArgument("yolo_enable", default_value="true"),
            DeclareLaunchArgument("yolo_threshold", default_value="0.5"),
            DeclareLaunchArgument("yolo_iou", default_value="0.7"),
            DeclareLaunchArgument("yolo_encoding", default_value="bgr8"),
            DeclareLaunchArgument("yolo_tracker", default_value="bytetrack.yaml"),
            DeclareLaunchArgument("yolo_imgsz_height", default_value="640"),
            DeclareLaunchArgument("yolo_imgsz_width", default_value="640"),
            DeclareLaunchArgument("yolo_half", default_value="false"),
            DeclareLaunchArgument("yolo_fuse_model", default_value="false"),
            DeclareLaunchArgument("yolo_max_det", default_value="300"),
            DeclareLaunchArgument(
                "yolo_input_image_topic",
                default_value="/shadow/perception/yolo_input_image",
            ),
            DeclareLaunchArgument("yolo_image_reliability", default_value="2"),
            DeclareLaunchArgument("yolo_namespace", default_value="yolo"),
            DeclareLaunchArgument("yolo_use_tracking", default_value="false"),
            DeclareLaunchArgument("yolo_use_debug", default_value="false"),
            DeclareLaunchArgument(
                "yolo_python_site",
                default_value=yolo_cuda_venv_site,
            ),
            DeclareLaunchArgument(
                "yolo_torch_lib",
                default_value=yolo_cuda_torch_lib,
            ),
            DeclareLaunchArgument("yolo_detections_topic", default_value="/yolo/detections"),
            DeclareLaunchArgument("target_point_topic", default_value="/shadow/route/target_point"),
            DeclareLaunchArgument("route_command_topic", default_value="/shadow/route/command"),
            DeclareLaunchArgument("route_target_publish_rate_hz", default_value="10.0"),
            DeclareLaunchArgument("route_target_lookahead_distance_m", default_value="15.0"),
            DeclareLaunchArgument(
                "route_target_source_priority",
                default_value="gui_route,image_lane,shadow_virtual",
            ),
            DeclareLaunchArgument(
                "route_target_publish_default_when_missing",
                default_value="true",
                description=(
                    "Publish a straight-ahead fallback target so E2E can keep running "
                    "when GUI/image/virtual route paths are temporarily empty."
                ),
            ),
            DeclareLaunchArgument("gui_route_path_topic", default_value="/shadow/route/gui_path"),
            DeclareLaunchArgument(
                "image_lane_path_topic", default_value="/shadow/perception/lane_path"
            ),
            DeclareLaunchArgument(
                "shadow_virtual_path_topic", default_value="/shadow/virtual/path"
            ),
            DeclareLaunchArgument("phone_bridge_server_host", default_value="0.0.0.0"),
            DeclareLaunchArgument("phone_bridge_server_port", default_value="8765"),
            DeclareLaunchArgument("phone_bridge_use_https", default_value="false"),
            DeclareLaunchArgument("phone_bridge_tls_cert_file", default_value=""),
            DeclareLaunchArgument("phone_bridge_tls_key_file", default_value=""),
            DeclareLaunchArgument(
                "phone_bridge_osrm_service_url",
                default_value="https://routing.openstreetmap.de/routed-car/route/v1/driving",
            ),
            DeclareLaunchArgument("phone_bridge_fix_topic", default_value="/phone/gps/fix"),
            DeclareLaunchArgument("phone_bridge_goal_topic", default_value="/phone/route/goal"),
            DeclareLaunchArgument(
                "phone_bridge_gps_status_topic", default_value="/vehicle/gps_status"
            ),
            DeclareLaunchArgument(
                "phone_bridge_status_topic", default_value="/phone/location/status"
            ),
            DeclareLaunchArgument("phone_bridge_route_command", default_value="lane_follow"),
            DeclareLaunchArgument("phone_bridge_auto_reroute_enabled", default_value="true"),
            DeclareLaunchArgument("phone_bridge_off_route_threshold_m", default_value="30.0"),
            DeclareLaunchArgument("phone_bridge_off_route_hold_sec", default_value="3.0"),
            DeclareLaunchArgument("phone_bridge_reroute_cooldown_sec", default_value="10.0"),
            DeclareLaunchArgument("camera_lane_detection_enabled", default_value="true"),
            DeclareLaunchArgument("camera_lane_detection_backend", default_value="opencv_classical"),
            DeclareLaunchArgument("camera_lane_detection_model_path", default_value=""),
            DeclareLaunchArgument(
                "camera_lane_detection_image_topic",
                default_value="/shadow/perception/lane_input_image",
            ),
            DeclareLaunchArgument(
                "camera_lane_detection_camera_info_topic",
                default_value="/shadow/perception/lane_input_camera_info",
            ),
            DeclareLaunchArgument(
                "camera_lane_detection_status_topic",
                default_value="/shadow/perception/lane_status",
            ),
            DeclareLaunchArgument(
                "camera_lane_detection_output_frame",
                default_value="base_link",
            ),
            DeclareLaunchArgument("camera_lane_detection_max_process_rate_hz", default_value="20.0"),
            DeclareLaunchArgument("camera_lane_detection_input_width", default_value="512"),
            DeclareLaunchArgument("camera_lane_detection_input_height", default_value="288"),
            DeclareLaunchArgument(
                "e2e_overlay_input_image_topic",
                default_value="/sensing/camera/camera0/image_rect_color",
            ),
            DeclareLaunchArgument("e2e_path_topic", default_value="/shadow/e2e/path"),
            DeclareLaunchArgument(
                "e2e_overlay_image_topic",
                default_value="/shadow/e2e/overlay_image",
            ),
            DeclareLaunchArgument(
                "e2e_overlay_compressed_image_topic",
                default_value="/shadow/e2e/overlay_image/compressed",
            ),
            DeclareLaunchArgument("e2e_overlay_compressed_jpeg_quality", default_value="80"),
            DeclareLaunchArgument("e2e_overlay_use_tf_translation", default_value="true"),
            DeclareLaunchArgument("e2e_overlay_output_max_edge_px", default_value="640"),
            DeclareLaunchArgument("e2e_overlay_process_rate_hz", default_value="10.0"),
            DeclareLaunchArgument("e2e_overlay_stale_image_timeout_sec", default_value="0.5"),
            DeclareLaunchArgument("require_target_point", default_value="true"),
            DeclareLaunchArgument("record_shadow_bag", default_value="false"),
            DeclareLaunchArgument(
                "bag_record_regex",
                default_value="(/shadow/.*|/livox/lane_detection/.*|/yolo/.*|/Odometry|/scan)",
            ),
            DeclareLaunchArgument("metrics_csv_logging", default_value="false"),
            DeclareLaunchArgument(
                "e2e_param_file",
                default_value=PathJoinSubstitution(
                    [e2e_share, "config", "e2e_transfuser.param.yaml"]
                ),
            ),
            DeclareLaunchArgument(
                "e2e_metrics_param_file",
                default_value=PathJoinSubstitution(
                    [e2e_metrics_share, "config", "shadow_mode_e2e_metrics.param.yaml"]
                ),
            ),
            DeclareLaunchArgument(
                "e2e_path_overlay_param_file",
                default_value=PathJoinSubstitution(
                    [e2e_path_overlay_share, "config", "e2e_path_overlay.param.yaml"]
                ),
            ),
            DeclareLaunchArgument("e2e_runtime_mode", default_value="lead_python"),
            DeclareLaunchArgument("e2e_precision_mode", default_value="fp32"),
            DeclareLaunchArgument("e2e_runtime_device", default_value="cuda:0"),
            DeclareLaunchArgument("e2e_input_preprocess_backend", default_value="cpu"),
            DeclareLaunchArgument(
                "e2e_model_input_image_topic",
                default_value="/shadow/e2e/model_input_image",
            ),
            DeclareLaunchArgument(
                "e2e_input_image_topic",
                default_value="/shadow/e2e/model_input_image",
            ),
            DeclareLaunchArgument("e2e_disable_image_fallback_topics", default_value="true"),
            DeclareLaunchArgument("e2e_model_input_width_px", default_value="1152"),
            DeclareLaunchArgument("e2e_model_input_height_px", default_value="384"),
            DeclareLaunchArgument(
                "e2e_yolo_input_image_topic",
                default_value="/shadow/perception/yolo_input_image",
            ),
            DeclareLaunchArgument("e2e_yolo_input_width_px", default_value="960"),
            DeclareLaunchArgument("e2e_yolo_input_height_px", default_value="640"),
            DeclareLaunchArgument(
                "e2e_lane_input_image_topic",
                default_value="/shadow/perception/lane_input_image",
            ),
            DeclareLaunchArgument(
                "e2e_lane_input_camera_info_topic",
                default_value="/shadow/perception/lane_input_camera_info",
            ),
            DeclareLaunchArgument("e2e_lane_input_width_px", default_value="640"),
            DeclareLaunchArgument("e2e_lane_input_height_px", default_value="427"),
            DeclareLaunchArgument("e2e_model_variant", default_value="tfv6_resnet34"),
            DeclareLaunchArgument("e2e_sensor_input_mode", default_value="auto"),
            DeclareLaunchArgument("e2e_camera_only_confidence_scale", default_value="0.75"),
            DeclareLaunchArgument(
                "e2e_model_path",
                default_value=lead_model_path,
            ),
            DeclareLaunchArgument("lead_project_root", default_value=lead_project_root_path),
            DeclareLaunchArgument("lead_python_site", default_value=yolo_cuda_venv_site),
            DeclareLaunchArgument("lead_torch_lib", default_value=yolo_cuda_torch_lib),
            DeclareLaunchArgument("lead_strict_weight_load", default_value="false"),
            DeclareLaunchArgument("lead_probe_on_startup", default_value="true"),
            DeclareLaunchArgument("lead_force_timm_pretrained_off", default_value="true"),
            DeclareLaunchArgument("disable_aux_heads", default_value="true"),
            DeclareLaunchArgument("single_checkpoint", default_value="true"),
            DeclareLaunchArgument("allow_int8", default_value="false"),
            DeclareLaunchArgument("e2e_publish_rate_hz", default_value="10.0"),
            DeclareLaunchArgument("e2e_metrics_publish_rate_hz", default_value="10.0"),
            DeclareLaunchArgument("input_timeout_sec", default_value="0.5"),
            camera_lidar_bringup,
            adas_description,
            fast_lio,
            livox_lane_detection,
            camera_lane_detection,
            shadow_mode,
            e2e_transfuser,
            e2e_metrics,
            e2e_path_overlay,
        ]
    )
