from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    fusion_share = FindPackageShare("shadow_mode_localization_fusion")

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "param_file",
                default_value=PathJoinSubstitution(
                    [fusion_share, "config", "shadow_localization_fusion.param.yaml"]
                ),
            ),
            DeclareLaunchArgument("lidar_odom_topic", default_value="/Odometry"),
            DeclareLaunchArgument("phone_fix_topic", default_value="/phone/gps/fix"),
            DeclareLaunchArgument("spresense_fix_topic", default_value="/spresense/gps/fix"),
            DeclareLaunchArgument("fused_odom_topic", default_value="/shadow/fused/odometry"),
            DeclareLaunchArgument("fused_path_topic", default_value="/shadow/fused/path"),
            DeclareLaunchArgument("status_topic", default_value="/shadow/fused/status"),
            DeclareLaunchArgument("fix_timeout_sec", default_value="3.0"),
            DeclareLaunchArgument("max_fix_accuracy_m", default_value="25.0"),
            DeclareLaunchArgument("correction_gain", default_value="0.08"),
            DeclareLaunchArgument("dynamic_correction_gain", default_value="true"),
            DeclareLaunchArgument("low_speed_threshold_mps", default_value="3.0"),
            DeclareLaunchArgument("high_speed_threshold_mps", default_value="20.0"),
            DeclareLaunchArgument("high_speed_correction_gain", default_value="0.01"),
            DeclareLaunchArgument("high_speed_max_correction_step_m", default_value="0.05"),
            Node(
                package="shadow_mode_localization_fusion",
                executable="shadow_localization_fusion_node.py",
                name="shadow_localization_fusion",
                output="screen",
                parameters=[
                    LaunchConfiguration("param_file"),
                    {
                        "lidar_odom_topic": LaunchConfiguration("lidar_odom_topic"),
                        "phone_fix_topic": LaunchConfiguration("phone_fix_topic"),
                        "spresense_fix_topic": LaunchConfiguration("spresense_fix_topic"),
                        "fused_odom_topic": LaunchConfiguration("fused_odom_topic"),
                        "fused_path_topic": LaunchConfiguration("fused_path_topic"),
                        "status_topic": LaunchConfiguration("status_topic"),
                        "fix_timeout_sec": ParameterValue(
                            LaunchConfiguration("fix_timeout_sec"), value_type=float
                        ),
                        "max_fix_accuracy_m": ParameterValue(
                            LaunchConfiguration("max_fix_accuracy_m"), value_type=float
                        ),
                        "correction_gain": ParameterValue(
                            LaunchConfiguration("correction_gain"), value_type=float
                        ),
                        "dynamic_correction_gain": ParameterValue(
                            LaunchConfiguration("dynamic_correction_gain"), value_type=bool
                        ),
                        "low_speed_threshold_mps": ParameterValue(
                            LaunchConfiguration("low_speed_threshold_mps"), value_type=float
                        ),
                        "high_speed_threshold_mps": ParameterValue(
                            LaunchConfiguration("high_speed_threshold_mps"), value_type=float
                        ),
                        "high_speed_correction_gain": ParameterValue(
                            LaunchConfiguration("high_speed_correction_gain"), value_type=float
                        ),
                        "high_speed_max_correction_step_m": ParameterValue(
                            LaunchConfiguration("high_speed_max_correction_step_m"),
                            value_type=float,
                        ),
                    },
                ],
            ),
        ]
    )
