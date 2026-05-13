from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    package_share = FindPackageShare("shadow_mode_e2e_metrics")
    param_file = LaunchConfiguration("param_file")

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "param_file",
                default_value=PathJoinSubstitution(
                    [package_share, "config", "shadow_mode_e2e_metrics.param.yaml"]
                ),
            ),
            DeclareLaunchArgument("publish_rate_hz", default_value="10.0"),
            DeclareLaunchArgument("input_timeout_sec", default_value="0.5"),
            DeclareLaunchArgument("wheel_base_m", default_value="2.7"),
            Node(
                package="shadow_mode_e2e_metrics",
                executable="shadow_mode_e2e_metrics_node.py",
                name="shadow_mode_e2e_metrics",
                output="screen",
                parameters=[
                    param_file,
                    {
                        "publish_rate_hz": ParameterValue(
                            LaunchConfiguration("publish_rate_hz"), value_type=float
                        ),
                        "input_timeout_sec": ParameterValue(
                            LaunchConfiguration("input_timeout_sec"), value_type=float
                        ),
                        "wheel_base_m": ParameterValue(
                            LaunchConfiguration("wheel_base_m"), value_type=float
                        ),
                    },
                ],
            ),
        ]
    )
