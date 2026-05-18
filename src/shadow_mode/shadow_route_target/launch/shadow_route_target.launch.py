from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    share = FindPackageShare("shadow_route_target")
    param_file = LaunchConfiguration("param_file")

    node = Node(
        package="shadow_route_target",
        executable="shadow_route_target_node.py",
        name="shadow_route_target",
        output="screen",
        parameters=[
            param_file,
            {
                "output_topic": LaunchConfiguration("output_topic"),
                "status_topic": LaunchConfiguration("status_topic"),
                "route_command_topic": LaunchConfiguration("route_command_topic"),
                "publish_route_command": ParameterValue(
                    LaunchConfiguration("publish_route_command"), value_type=bool
                ),
                "route_command": LaunchConfiguration("route_command"),
                "publish_rate_hz": ParameterValue(
                    LaunchConfiguration("publish_rate_hz"), value_type=float
                ),
                "input_timeout_sec": ParameterValue(
                    LaunchConfiguration("input_timeout_sec"), value_type=float
                ),
                "lookahead_distance_m": ParameterValue(
                    LaunchConfiguration("lookahead_distance_m"), value_type=float
                ),
                "min_forward_distance_m": ParameterValue(
                    LaunchConfiguration("min_forward_distance_m"), value_type=float
                ),
                "source_priority": LaunchConfiguration("source_priority"),
                "gui_route_path_topic": LaunchConfiguration("gui_route_path_topic"),
                "image_lane_path_topic": LaunchConfiguration("image_lane_path_topic"),
                "shadow_virtual_path_topic": LaunchConfiguration("shadow_virtual_path_topic"),
                "default_frame_id": LaunchConfiguration("default_frame_id"),
                "default_target_x_m": ParameterValue(
                    LaunchConfiguration("default_target_x_m"), value_type=float
                ),
                "default_target_y_m": ParameterValue(
                    LaunchConfiguration("default_target_y_m"), value_type=float
                ),
                "publish_default_when_missing": ParameterValue(
                    LaunchConfiguration("publish_default_when_missing"), value_type=bool
                ),
            },
        ],
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "param_file",
                default_value=PathJoinSubstitution(
                    [share, "config", "shadow_route_target.param.yaml"]
                ),
            ),
            DeclareLaunchArgument("output_topic", default_value="/shadow/route/target_point"),
            DeclareLaunchArgument("status_topic", default_value="/shadow/route/target_status"),
            DeclareLaunchArgument("route_command_topic", default_value="/shadow/route/command"),
            DeclareLaunchArgument("publish_route_command", default_value="true"),
            DeclareLaunchArgument("route_command", default_value="lane_follow"),
            DeclareLaunchArgument("publish_rate_hz", default_value="10.0"),
            DeclareLaunchArgument("input_timeout_sec", default_value="0.5"),
            DeclareLaunchArgument("lookahead_distance_m", default_value="15.0"),
            DeclareLaunchArgument("min_forward_distance_m", default_value="1.0"),
            DeclareLaunchArgument(
                "source_priority", default_value="gui_route,image_lane,shadow_virtual"
            ),
            DeclareLaunchArgument("gui_route_path_topic", default_value="/shadow/route/gui_path"),
            DeclareLaunchArgument(
                "image_lane_path_topic", default_value="/shadow/perception/lane_path"
            ),
            DeclareLaunchArgument(
                "shadow_virtual_path_topic", default_value="/shadow/virtual/path"
            ),
            DeclareLaunchArgument("default_frame_id", default_value="base_link"),
            DeclareLaunchArgument("default_target_x_m", default_value="15.0"),
            DeclareLaunchArgument("default_target_y_m", default_value="0.0"),
            DeclareLaunchArgument("publish_default_when_missing", default_value="false"),
            node,
        ]
    )
