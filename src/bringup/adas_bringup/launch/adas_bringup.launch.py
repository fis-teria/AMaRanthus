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
    lane_detection_model_path = LaunchConfiguration("lane_detection_model_path")
    lane_detection_colored_cloud_topic = LaunchConfiguration(
        "lane_detection_colored_cloud_topic"
    )
    lane_detection_scan_topic = LaunchConfiguration("lane_detection_scan_topic")
    lane_detection_objects_topic = LaunchConfiguration("lane_detection_objects_topic")
    lane_detection_output_frame = LaunchConfiguration("lane_detection_output_frame")

    livox_share = FindPackageShare("livox_ros_driver2")
    adas_bringup_share = FindPackageShare("adas_bringup")
    livox_lane_detection_share = FindPackageShare("livox_lane_detection")

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

    livox_lane_detection_launch = IncludeLaunchDescription(
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
            "pointcloud_topic": pointcloud_topic,
            "model_path": lane_detection_model_path,
            "colored_cloud_topic": lane_detection_colored_cloud_topic,
            "lane_scan_topic": lane_detection_scan_topic,
            "objects_topic": lane_detection_objects_topic,
            "output_frame": lane_detection_output_frame,
            "launch_livox_driver": "false",
        }.items(),
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
            DeclareLaunchArgument(
                "lane_detection_model_path",
                default_value=PathJoinSubstitution(
                    [livox_lane_detection_share, "model", "livox_lane_det.ts"]
                ),
                description="livox_lane_detection が使用する TorchScript モデルパス",
            ),
            DeclareLaunchArgument(
                "lane_detection_colored_cloud_topic",
                default_value="/livox/lane_detection/points_with_class",
                description="livox_lane_detection が出力する色付き点群トピック名",
            ),
            DeclareLaunchArgument(
                "lane_detection_scan_topic",
                default_value="/livox/lane_detection/scan",
                description="livox_lane_detection が出力する lane scan トピック名",
            ),
            DeclareLaunchArgument(
                "lane_detection_objects_topic",
                default_value="/livox/lane_detection/objects",
                description="livox_lane_detection が出力する障害物トピック名",
            ),
            DeclareLaunchArgument(
                "lane_detection_output_frame",
                default_value="",
                description="livox_lane_detection の出力フレーム上書き設定",
            ),
            livox_msg_launch,
            livox_rviz_launch,
            livox_lane_detection_launch,
            pointcloud_to_laserscan_node,
        ]
    )
