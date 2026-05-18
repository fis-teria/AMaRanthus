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
            DeclareLaunchArgument(
                "image_topic",
                default_value="/sensing/camera/camera0/image_rect_color",
            ),
            DeclareLaunchArgument("disable_image_fallback_topics", default_value="false"),
            DeclareLaunchArgument(
                "camera_info_topic",
                default_value="/sensing/camera/camera0/camera_info",
            ),
            DeclareLaunchArgument("pointcloud_topic", default_value="/livox/lidar"),
            DeclareLaunchArgument("sensor_input_mode", default_value="auto"),
            DeclareLaunchArgument("odom_topic", default_value="/Odometry"),
            DeclareLaunchArgument("target_point_topic", default_value="/shadow/route/target_point"),
            DeclareLaunchArgument("route_command_topic", default_value="/shadow/route/command"),
            DeclareLaunchArgument("output_frame", default_value="base_link"),
            DeclareLaunchArgument("publish_rate_hz", default_value="10.0"),
            DeclareLaunchArgument("input_timeout_sec", default_value="0.5"),
            DeclareLaunchArgument("camera_only_confidence_scale", default_value="0.75"),
            DeclareLaunchArgument("max_waypoints", default_value="10"),
            DeclareLaunchArgument("waypoint_spacing_m", default_value="1.5"),
            DeclareLaunchArgument("wheel_base_m", default_value="2.7"),
            DeclareLaunchArgument("require_target_point", default_value="true"),
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
                        "image_topic": LaunchConfiguration("image_topic"),
                        "disable_image_fallback_topics": ParameterValue(
                            LaunchConfiguration("disable_image_fallback_topics"),
                            value_type=bool,
                        ),
                        "camera_info_topic": LaunchConfiguration("camera_info_topic"),
                        "pointcloud_topic": LaunchConfiguration("pointcloud_topic"),
                        "sensor_input_mode": LaunchConfiguration("sensor_input_mode"),
                        "odom_topic": LaunchConfiguration("odom_topic"),
                        "target_point_topic": LaunchConfiguration("target_point_topic"),
                        "route_command_topic": LaunchConfiguration("route_command_topic"),
                        "output_frame": LaunchConfiguration("output_frame"),
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
