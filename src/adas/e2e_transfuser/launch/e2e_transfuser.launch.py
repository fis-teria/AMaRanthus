from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import EnvironmentVariable, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    package_share = FindPackageShare("e2e_transfuser")
    param_file = LaunchConfiguration("param_file")

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "param_file",
                default_value=PathJoinSubstitution(
                    [package_share, "config", "e2e_transfuser.param.yaml"]
                ),
            ),
            DeclareLaunchArgument("runtime_mode", default_value="mock"),
            DeclareLaunchArgument("precision_mode", default_value="fp32"),
            DeclareLaunchArgument("model_variant", default_value="tfv6_resnet34"),
            DeclareLaunchArgument("model_path", default_value="Data/models/tfv6/tfv6_resnet34"),
            DeclareLaunchArgument("lead_project_root", default_value=""),
            DeclareLaunchArgument("lead_python_site", default_value=""),
            DeclareLaunchArgument("lead_torch_lib", default_value=""),
            DeclareLaunchArgument("runtime_device", default_value="cuda:0"),
            DeclareLaunchArgument("input_preprocess_backend", default_value="cpu"),
            DeclareLaunchArgument("lead_strict_weight_load", default_value="false"),
            DeclareLaunchArgument("lead_probe_on_startup", default_value="true"),
            DeclareLaunchArgument("lead_force_timm_pretrained_off", default_value="true"),
            DeclareLaunchArgument("lead_lidar_raster_enabled", default_value="true"),
            DeclareLaunchArgument("lead_lidar_flip_y_axis", default_value="true"),
            DeclareLaunchArgument("lead_lidar_history_size", default_value="1"),
            DeclareLaunchArgument("lead_lidar_max_points", default_value="250000"),
            DeclareLaunchArgument(
                "lead_lidar_expected_frame_ids",
                default_value="body,base_link",
            ),
            DeclareLaunchArgument(
                "image_topic",
                default_value="/sensing/camera/camera0/image_rect_color",
            ),
            DeclareLaunchArgument("disable_image_fallback_topics", default_value="false"),
            DeclareLaunchArgument(
                "camera_info_topic",
                default_value="/sensing/camera/camera0/camera_info",
            ),
            DeclareLaunchArgument("synthesize_camera_info_when_missing", default_value="false"),
            DeclareLaunchArgument("synthetic_camera_info_focal_length_px", default_value="0.0"),
            DeclareLaunchArgument("synthetic_camera_info_frame_id", default_value=""),
            DeclareLaunchArgument("pointcloud_topic", default_value="/livox/lidar"),
            DeclareLaunchArgument("sensor_input_mode", default_value="auto"),
            DeclareLaunchArgument("odom_topic", default_value="/Odometry"),
            DeclareLaunchArgument("target_point_topic", default_value="/shadow/route/target_point"),
            DeclareLaunchArgument("target_path_topic", default_value="/shadow/route/target_path"),
            DeclareLaunchArgument("use_target_path_triplet", default_value="true"),
            DeclareLaunchArgument("target_path_previous_distance_m", default_value="5.0"),
            DeclareLaunchArgument("target_path_current_distance_m", default_value="15.0"),
            DeclareLaunchArgument("target_path_next_distance_m", default_value="25.0"),
            DeclareLaunchArgument("target_path_speed_adaptive", default_value="true"),
            DeclareLaunchArgument("target_path_speed_lookahead_time_sec", default_value="1.2"),
            DeclareLaunchArgument("target_path_max_current_distance_m", default_value="60.0"),
            DeclareLaunchArgument("target_path_min_forward_distance_m", default_value="0.5"),
            DeclareLaunchArgument(
                "target_path_expected_frame_ids",
                default_value="base_link,body",
            ),
            DeclareLaunchArgument("target_path_require_expected_frame", default_value="true"),
            DeclareLaunchArgument("route_command_topic", default_value="/shadow/route/command"),
            DeclareLaunchArgument("output_frame", default_value="base_link"),
            DeclareLaunchArgument(
                "raw_lead_path_topic",
                default_value="/shadow/e2e/path_raw_lead",
            ),
            DeclareLaunchArgument("publish_rate_hz", default_value="10.0"),
            DeclareLaunchArgument("input_timeout_sec", default_value="0.5"),
            DeclareLaunchArgument("camera_only_confidence_scale", default_value="0.75"),
            DeclareLaunchArgument("max_waypoints", default_value="10"),
            DeclareLaunchArgument("waypoint_spacing_m", default_value="1.5"),
            DeclareLaunchArgument("wheel_base_m", default_value="2.7"),
            DeclareLaunchArgument("require_target_point", default_value="true"),
            DeclareLaunchArgument("lead_flip_y_axis", default_value="true"),
            DeclareLaunchArgument("disable_aux_heads", default_value="true"),
            DeclareLaunchArgument("single_checkpoint", default_value="true"),
            DeclareLaunchArgument("allow_int8", default_value="false"),
            Node(
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
                    param_file,
                    {
                        "runtime_mode": LaunchConfiguration("runtime_mode"),
                        "precision_mode": LaunchConfiguration("precision_mode"),
                        "model_variant": LaunchConfiguration("model_variant"),
                        "model_path": LaunchConfiguration("model_path"),
                        "lead_project_root": LaunchConfiguration("lead_project_root"),
                        "lead_python_site": LaunchConfiguration("lead_python_site"),
                        "lead_torch_lib": LaunchConfiguration("lead_torch_lib"),
                        "runtime_device": LaunchConfiguration("runtime_device"),
                        "input_preprocess_backend": LaunchConfiguration(
                            "input_preprocess_backend"
                        ),
                        "lead_strict_weight_load": ParameterValue(
                            LaunchConfiguration("lead_strict_weight_load"), value_type=bool
                        ),
                        "lead_probe_on_startup": ParameterValue(
                            LaunchConfiguration("lead_probe_on_startup"), value_type=bool
                        ),
                        "lead_force_timm_pretrained_off": ParameterValue(
                            LaunchConfiguration("lead_force_timm_pretrained_off"), value_type=bool
                        ),
                        "lead_lidar_raster_enabled": ParameterValue(
                            LaunchConfiguration("lead_lidar_raster_enabled"),
                            value_type=bool,
                        ),
                        "lead_lidar_flip_y_axis": ParameterValue(
                            LaunchConfiguration("lead_lidar_flip_y_axis"),
                            value_type=bool,
                        ),
                        "lead_lidar_history_size": ParameterValue(
                            LaunchConfiguration("lead_lidar_history_size"),
                            value_type=int,
                        ),
                        "lead_lidar_max_points": ParameterValue(
                            LaunchConfiguration("lead_lidar_max_points"),
                            value_type=int,
                        ),
                        "lead_lidar_expected_frame_ids": LaunchConfiguration(
                            "lead_lidar_expected_frame_ids"
                        ),
                        "image_topic": LaunchConfiguration("image_topic"),
                        "disable_image_fallback_topics": ParameterValue(
                            LaunchConfiguration("disable_image_fallback_topics"),
                            value_type=bool,
                        ),
                        "camera_info_topic": LaunchConfiguration("camera_info_topic"),
                        "synthesize_camera_info_when_missing": ParameterValue(
                            LaunchConfiguration("synthesize_camera_info_when_missing"),
                            value_type=bool,
                        ),
                        "synthetic_camera_info_focal_length_px": ParameterValue(
                            LaunchConfiguration("synthetic_camera_info_focal_length_px"),
                            value_type=float,
                        ),
                        "synthetic_camera_info_frame_id": LaunchConfiguration(
                            "synthetic_camera_info_frame_id"
                        ),
                        "pointcloud_topic": LaunchConfiguration("pointcloud_topic"),
                        "sensor_input_mode": LaunchConfiguration("sensor_input_mode"),
                        "odom_topic": LaunchConfiguration("odom_topic"),
                        "target_point_topic": LaunchConfiguration("target_point_topic"),
                        "target_path_topic": LaunchConfiguration("target_path_topic"),
                        "use_target_path_triplet": ParameterValue(
                            LaunchConfiguration("use_target_path_triplet"), value_type=bool
                        ),
                        "target_path_previous_distance_m": ParameterValue(
                            LaunchConfiguration("target_path_previous_distance_m"),
                            value_type=float,
                        ),
                        "target_path_current_distance_m": ParameterValue(
                            LaunchConfiguration("target_path_current_distance_m"),
                            value_type=float,
                        ),
                        "target_path_next_distance_m": ParameterValue(
                            LaunchConfiguration("target_path_next_distance_m"),
                            value_type=float,
                        ),
                        "target_path_speed_adaptive": ParameterValue(
                            LaunchConfiguration("target_path_speed_adaptive"),
                            value_type=bool,
                        ),
                        "target_path_speed_lookahead_time_sec": ParameterValue(
                            LaunchConfiguration("target_path_speed_lookahead_time_sec"),
                            value_type=float,
                        ),
                        "target_path_max_current_distance_m": ParameterValue(
                            LaunchConfiguration("target_path_max_current_distance_m"),
                            value_type=float,
                        ),
                        "target_path_min_forward_distance_m": ParameterValue(
                            LaunchConfiguration("target_path_min_forward_distance_m"),
                            value_type=float,
                        ),
                        "target_path_expected_frame_ids": LaunchConfiguration(
                            "target_path_expected_frame_ids"
                        ),
                        "target_path_require_expected_frame": ParameterValue(
                            LaunchConfiguration("target_path_require_expected_frame"),
                            value_type=bool,
                        ),
                        "route_command_topic": LaunchConfiguration("route_command_topic"),
                        "output_frame": LaunchConfiguration("output_frame"),
                        "raw_lead_path_topic": LaunchConfiguration("raw_lead_path_topic"),
                        "publish_rate_hz": ParameterValue(
                            LaunchConfiguration("publish_rate_hz"), value_type=float
                        ),
                        "input_timeout_sec": ParameterValue(
                            LaunchConfiguration("input_timeout_sec"), value_type=float
                        ),
                        "camera_only_confidence_scale": ParameterValue(
                            LaunchConfiguration("camera_only_confidence_scale"), value_type=float
                        ),
                        "max_waypoints": ParameterValue(
                            LaunchConfiguration("max_waypoints"), value_type=int
                        ),
                        "waypoint_spacing_m": ParameterValue(
                            LaunchConfiguration("waypoint_spacing_m"), value_type=float
                        ),
                        "wheel_base_m": ParameterValue(
                            LaunchConfiguration("wheel_base_m"), value_type=float
                        ),
                        "require_target_point": ParameterValue(
                            LaunchConfiguration("require_target_point"), value_type=bool
                        ),
                        "lead_flip_y_axis": ParameterValue(
                            LaunchConfiguration("lead_flip_y_axis"), value_type=bool
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
                    },
                ],
            ),
        ]
    )
