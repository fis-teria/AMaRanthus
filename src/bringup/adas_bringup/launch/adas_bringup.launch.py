from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition, UnlessCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    use_livox_rviz = LaunchConfiguration("use_livox_rviz")
    pointcloud_topic = LaunchConfiguration("pointcloud_topic")
    scan_topic = LaunchConfiguration("scan_topic")
    pointcloud_to_laserscan_param_file = LaunchConfiguration(
        "pointcloud_to_laserscan_param_file"
    )

    livox_share = FindPackageShare("livox_ros_driver2")
    adas_bringup_share = FindPackageShare("adas_bringup")

    livox_msg_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([livox_share, "launch_ROS2", "msg_HAP_launch.py"])
        ),
        condition=UnlessCondition(use_livox_rviz),
    )

    livox_rviz_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([livox_share, "launch_ROS2", "rviz_HAP_launch.py"])
        ),
        condition=IfCondition(use_livox_rviz),
    )

    pointcloud_to_laserscan_node = Node(
        package="pointcloud_to_laserscan",
        executable="pointcloud_to_laserscan_node",
        name="pointcloud_to_laserscan",
        output="screen",
        parameters=[pointcloud_to_laserscan_param_file],
        remappings=[
            ("cloud_in", pointcloud_topic),
            ("scan", scan_topic),
        ],
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "use_livox_rviz",
                default_value="true",
                description=(
                    "true のとき rviz_HAP_launch.py、false のとき msg_HAP_launch.py を使用します。"
                ),
            ),
            DeclareLaunchArgument(
                "pointcloud_topic",
                default_value="/livox/lidar",
                description="pointcloud_to_laserscan が購読する PointCloud2 トピック名",
            ),
            DeclareLaunchArgument(
                "scan_topic",
                default_value="/scan",
                description="pointcloud_to_laserscan が出力する LaserScan トピック名",
            ),
            DeclareLaunchArgument(
                "pointcloud_to_laserscan_param_file",
                default_value=PathJoinSubstitution(
                    [adas_bringup_share, "config", "pointcloud_to_laserscan.yaml"]
                ),
                description="pointcloud_to_laserscan のパラメータファイル",
            ),
            livox_msg_launch,
            livox_rviz_launch,
            pointcloud_to_laserscan_node,
        ]
    )
