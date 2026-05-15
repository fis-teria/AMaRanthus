import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.actions import GroupAction
from launch.actions import IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import AnyLaunchDescriptionSource
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import EnvironmentVariable
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def make_relay(name, input_topic, output_topic):
    return Node(
        package="topic_tools",
        executable="relay",
        name=name,
        arguments=[input_topic, output_topic],
        output="screen",
        condition=IfCondition(LaunchConfiguration("use_autoware_topic_bridge")),
    )


def generate_launch_description():
    shadow_bringup_share = get_package_share_directory("shadow_mode_bringup")
    autoware_launch_share = get_package_share_directory("autoware_launch")

    map_path = LaunchConfiguration("map_path")
    vehicle_model = LaunchConfiguration("vehicle_model")
    sensor_model = LaunchConfiguration("sensor_model")
    data_path = LaunchConfiguration("data_path")
    use_sim_time = LaunchConfiguration("use_sim_time")

    livox_pointcloud_topic = LaunchConfiguration("livox_pointcloud_topic")
    odom_topic = LaunchConfiguration("odom_topic")
    autoware_concatenated_pointcloud_topic = LaunchConfiguration(
        "autoware_concatenated_pointcloud_topic"
    )
    autoware_top_pointcloud_topic = LaunchConfiguration("autoware_top_pointcloud_topic")
    autoware_kinematic_state_topic = LaunchConfiguration("autoware_kinematic_state_topic")

    shadow_mode = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                shadow_bringup_share,
                "launch",
                "shadow_mode_bringup.launch.py",
            )
        ),
        launch_arguments={
            "use_adas_bringup": LaunchConfiguration("use_adas_bringup"),
            "use_livox_rviz": LaunchConfiguration("use_livox_rviz"),
            "use_fast_lio": LaunchConfiguration("use_fast_lio"),
            "use_sim_time": use_sim_time,
            "fast_lio_config_path": LaunchConfiguration("fast_lio_config_path"),
            "fast_lio_config_file": LaunchConfiguration("fast_lio_config_file"),
            "use_fast_lio_rviz": LaunchConfiguration("use_fast_lio_rviz"),
            "fast_lio_rviz_cfg": LaunchConfiguration("fast_lio_rviz_cfg"),
            "use_ego_estimation": LaunchConfiguration("use_ego_estimation"),
            "use_virtual_control": LaunchConfiguration("use_virtual_control"),
            "use_metrics": LaunchConfiguration("use_metrics"),
            "pointcloud_topic": livox_pointcloud_topic,
            "scan_topic": LaunchConfiguration("scan_topic"),
            "virtual_input_mode": LaunchConfiguration("virtual_input_mode"),
            "virtual_pointcloud_topic": livox_pointcloud_topic,
            "odom_topic": odom_topic,
            "record_shadow_bag": LaunchConfiguration("record_shadow_bag"),
            "metrics_csv_logging": LaunchConfiguration("metrics_csv_logging"),
            "metrics_csv_path": LaunchConfiguration("metrics_csv_path"),
            "bag_output": LaunchConfiguration("bag_output"),
        }.items(),
        condition=IfCondition(LaunchConfiguration("launch_shadow_mode")),
    )

    autoware = IncludeLaunchDescription(
        AnyLaunchDescriptionSource(
            os.path.join(autoware_launch_share, "launch", "autoware.launch.xml")
        ),
        launch_arguments={
            "map_path": map_path,
            "vehicle_model": vehicle_model,
            "sensor_model": sensor_model,
            "data_path": data_path,
            "use_sim_time": use_sim_time,
            "rviz": LaunchConfiguration("rviz"),
            "planning_setting": LaunchConfiguration("planning_setting"),
            "planning_module_preset": LaunchConfiguration("planning_module_preset"),
            "control_module_preset": LaunchConfiguration("control_module_preset"),
            "launch_vehicle": LaunchConfiguration("launch_autoware_vehicle"),
            "launch_vehicle_interface": "false",
            "launch_system": LaunchConfiguration("launch_autoware_system"),
            "launch_map": LaunchConfiguration("launch_autoware_map"),
            "launch_sensing": "false",
            "launch_sensing_driver": "false",
            "launch_localization": "false",
            "launch_perception": LaunchConfiguration("launch_autoware_perception"),
            "launch_planning": LaunchConfiguration("launch_autoware_planning"),
            "launch_control": LaunchConfiguration("launch_autoware_control"),
            "launch_api": LaunchConfiguration("launch_autoware_api"),
            "is_simulation": LaunchConfiguration("is_simulation"),
        }.items(),
        condition=IfCondition(LaunchConfiguration("launch_autoware")),
    )

    topic_bridge = GroupAction(
        [
            make_relay(
                "livox_to_autoware_concatenated_pointcloud",
                livox_pointcloud_topic,
                autoware_concatenated_pointcloud_topic,
            ),
            make_relay(
                "livox_to_autoware_top_pointcloud",
                livox_pointcloud_topic,
                autoware_top_pointcloud_topic,
            ),
            make_relay(
                "odometry_to_autoware_kinematic_state",
                odom_topic,
                autoware_kinematic_state_topic,
            ),
        ]
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "map_path",
                default_value="",
                description="Autoware map directory. Required when launch_autoware:=true.",
            ),
            DeclareLaunchArgument("vehicle_model", default_value="sample_vehicle"),
            DeclareLaunchArgument("sensor_model", default_value="sample_sensor_kit"),
            DeclareLaunchArgument(
                "data_path",
                default_value=[EnvironmentVariable("HOME"), "/autoware_data"],
            ),
            DeclareLaunchArgument("use_sim_time", default_value="false"),
            DeclareLaunchArgument("launch_shadow_mode", default_value="true"),
            DeclareLaunchArgument("launch_autoware", default_value="true"),
            DeclareLaunchArgument("use_autoware_topic_bridge", default_value="true"),
            DeclareLaunchArgument("use_adas_bringup", default_value="true"),
            DeclareLaunchArgument("use_livox_rviz", default_value="false"),
            DeclareLaunchArgument(
                "use_fast_lio",
                default_value=LaunchConfiguration("use_adas_bringup"),
            ),
            DeclareLaunchArgument("fast_lio_config_path", default_value=""),
            DeclareLaunchArgument("fast_lio_config_file", default_value="mid360.yaml"),
            DeclareLaunchArgument("use_fast_lio_rviz", default_value="false"),
            DeclareLaunchArgument("fast_lio_rviz_cfg", default_value=""),
            DeclareLaunchArgument("use_ego_estimation", default_value="true"),
            DeclareLaunchArgument("use_virtual_control", default_value="true"),
            DeclareLaunchArgument("use_metrics", default_value="true"),
            DeclareLaunchArgument("record_shadow_bag", default_value="false"),
            DeclareLaunchArgument("metrics_csv_logging", default_value="false"),
            DeclareLaunchArgument(
                "metrics_csv_path",
                default_value="Data/metrics/shadow_mode_metrics.csv",
            ),
            DeclareLaunchArgument(
                "bag_output",
                default_value="Data/rosbag/shadow_mode_bag",
            ),
            DeclareLaunchArgument("livox_pointcloud_topic", default_value="/livox/lidar"),
            DeclareLaunchArgument("scan_topic", default_value="/scan"),
            DeclareLaunchArgument("virtual_input_mode", default_value="scan"),
            DeclareLaunchArgument("odom_topic", default_value="/Odometry"),
            DeclareLaunchArgument(
                "autoware_concatenated_pointcloud_topic",
                default_value="/sensing/lidar/concatenated/pointcloud",
            ),
            DeclareLaunchArgument(
                "autoware_top_pointcloud_topic",
                default_value="/sensing/lidar/top/pointcloud_raw_ex",
            ),
            DeclareLaunchArgument(
                "autoware_kinematic_state_topic",
                default_value="/localization/kinematic_state",
            ),
            DeclareLaunchArgument("planning_setting", default_value="rule_based"),
            DeclareLaunchArgument("planning_module_preset", default_value="default"),
            DeclareLaunchArgument("control_module_preset", default_value="default"),
            DeclareLaunchArgument("launch_autoware_vehicle", default_value="true"),
            DeclareLaunchArgument("launch_autoware_system", default_value="false"),
            DeclareLaunchArgument("launch_autoware_map", default_value="true"),
            DeclareLaunchArgument("launch_autoware_perception", default_value="true"),
            DeclareLaunchArgument("launch_autoware_planning", default_value="true"),
            DeclareLaunchArgument("launch_autoware_control", default_value="false"),
            DeclareLaunchArgument("launch_autoware_api", default_value="false"),
            DeclareLaunchArgument("rviz", default_value="false"),
            DeclareLaunchArgument("is_simulation", default_value="false"),
            shadow_mode,
            topic_bridge,
            autoware,
        ]
    )
