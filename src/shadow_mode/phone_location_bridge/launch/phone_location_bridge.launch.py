from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    node = Node(
        package="phone_location_bridge",
        executable="phone_location_bridge_node.py",
        name="phone_location_bridge",
        output="screen",
        parameters=[
            {
                "server_host": LaunchConfiguration("server_host"),
                "server_port": ParameterValue(
                    LaunchConfiguration("server_port"), value_type=int
                ),
                "use_https": ParameterValue(
                    LaunchConfiguration("use_https"), value_type=bool
                ),
                "tls_cert_file": LaunchConfiguration("tls_cert_file"),
                "tls_key_file": LaunchConfiguration("tls_key_file"),
                "osrm_service_url": LaunchConfiguration("osrm_service_url"),
                "publish_rate_hz": ParameterValue(
                    LaunchConfiguration("publish_rate_hz"), value_type=float
                ),
                "fix_stale_timeout_sec": ParameterValue(
                    LaunchConfiguration("fix_stale_timeout_sec"), value_type=float
                ),
                "fix_topic": LaunchConfiguration("fix_topic"),
                "goal_topic": LaunchConfiguration("goal_topic"),
                "route_path_topic": LaunchConfiguration("route_path_topic"),
                "gps_status_topic": LaunchConfiguration("gps_status_topic"),
                "status_topic": LaunchConfiguration("status_topic"),
                "route_frame_id": LaunchConfiguration("route_frame_id"),
                "path_step_m": ParameterValue(
                    LaunchConfiguration("path_step_m"), value_type=float
                ),
                "max_path_length_m": ParameterValue(
                    LaunchConfiguration("max_path_length_m"), value_type=float
                ),
                "default_heading_deg": ParameterValue(
                    LaunchConfiguration("default_heading_deg"), value_type=float
                ),
                "assume_heading_to_goal": ParameterValue(
                    LaunchConfiguration("assume_heading_to_goal"), value_type=bool
                ),
                "route_command_topic": LaunchConfiguration("route_command_topic"),
                "route_command": LaunchConfiguration("route_command"),
                "auto_reroute_enabled": ParameterValue(
                    LaunchConfiguration("auto_reroute_enabled"), value_type=bool
                ),
                "off_route_threshold_m": ParameterValue(
                    LaunchConfiguration("off_route_threshold_m"), value_type=float
                ),
                "off_route_hold_sec": ParameterValue(
                    LaunchConfiguration("off_route_hold_sec"), value_type=float
                ),
                "reroute_cooldown_sec": ParameterValue(
                    LaunchConfiguration("reroute_cooldown_sec"), value_type=float
                ),
            }
        ],
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("server_host", default_value="0.0.0.0"),
            DeclareLaunchArgument("server_port", default_value="8765"),
            DeclareLaunchArgument("use_https", default_value="false"),
            DeclareLaunchArgument("tls_cert_file", default_value=""),
            DeclareLaunchArgument("tls_key_file", default_value=""),
            DeclareLaunchArgument(
                "osrm_service_url",
                default_value="https://routing.openstreetmap.de/routed-car/route/v1/driving",
            ),
            DeclareLaunchArgument("publish_rate_hz", default_value="10.0"),
            DeclareLaunchArgument("fix_stale_timeout_sec", default_value="3.0"),
            DeclareLaunchArgument("fix_topic", default_value="/phone/gps/fix"),
            DeclareLaunchArgument("goal_topic", default_value="/phone/route/goal"),
            DeclareLaunchArgument("route_path_topic", default_value="/shadow/route/gui_path"),
            DeclareLaunchArgument("gps_status_topic", default_value="/vehicle/gps_status"),
            DeclareLaunchArgument("status_topic", default_value="/phone/location/status"),
            DeclareLaunchArgument("route_frame_id", default_value="base_link"),
            DeclareLaunchArgument("path_step_m", default_value="2.0"),
            DeclareLaunchArgument("max_path_length_m", default_value="400.0"),
            DeclareLaunchArgument("default_heading_deg", default_value="0.0"),
            DeclareLaunchArgument("assume_heading_to_goal", default_value="true"),
            DeclareLaunchArgument("route_command_topic", default_value="/shadow/route/command"),
            DeclareLaunchArgument("route_command", default_value="lane_follow"),
            DeclareLaunchArgument("auto_reroute_enabled", default_value="true"),
            DeclareLaunchArgument("off_route_threshold_m", default_value="30.0"),
            DeclareLaunchArgument("off_route_hold_sec", default_value="3.0"),
            DeclareLaunchArgument("reroute_cooldown_sec", default_value="10.0"),
            node,
        ]
    )
