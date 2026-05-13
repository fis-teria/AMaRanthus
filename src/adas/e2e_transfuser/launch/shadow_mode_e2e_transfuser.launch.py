from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    e2e_share = FindPackageShare("e2e_transfuser")
    shadow_bringup_share = FindPackageShare("shadow_mode_bringup")
    e2e_metrics_share = FindPackageShare("shadow_mode_e2e_metrics")

    use_shadow_mode_bringup = LaunchConfiguration("use_shadow_mode_bringup")
    use_e2e_transfuser = LaunchConfiguration("use_e2e_transfuser")
    use_e2e_metrics = LaunchConfiguration("use_e2e_metrics")

    e2e_param_file = LaunchConfiguration("e2e_param_file")
    e2e_metrics_param_file = LaunchConfiguration("e2e_metrics_param_file")

    shadow_mode = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution(
                [shadow_bringup_share, "launch", "shadow_mode_bringup.launch.py"]
            )
        ),
        launch_arguments={
            "use_adas_bringup": LaunchConfiguration("use_adas_bringup"),
            "virtual_input_mode": LaunchConfiguration("virtual_input_mode"),
            "lane_detection_scan_topic": LaunchConfiguration("lane_detection_scan_topic"),
            "virtual_pointcloud_topic": LaunchConfiguration("pointcloud_topic"),
            "pointcloud_topic": LaunchConfiguration("pointcloud_topic"),
            "odom_topic": LaunchConfiguration("odom_topic"),
            "record_shadow_bag": LaunchConfiguration("record_shadow_bag"),
            "bag_record_regex": LaunchConfiguration("bag_record_regex"),
            "metrics_csv_logging": LaunchConfiguration("metrics_csv_logging"),
        }.items(),
        condition=IfCondition(use_shadow_mode_bringup),
    )

    e2e_transfuser = Node(
        package="e2e_transfuser",
        executable="e2e_transfuser_node.py",
        name="e2e_transfuser",
        output="screen",
        parameters=[
            e2e_param_file,
            {
                "runtime_mode": LaunchConfiguration("e2e_runtime_mode"),
                "precision_mode": LaunchConfiguration("e2e_precision_mode"),
                "model_variant": LaunchConfiguration("e2e_model_variant"),
                "model_path": LaunchConfiguration("e2e_model_path"),
                "lead_project_root": LaunchConfiguration("lead_project_root"),
                "image_topic": LaunchConfiguration("image_topic"),
                "camera_info_topic": LaunchConfiguration("camera_info_topic"),
                "pointcloud_topic": LaunchConfiguration("pointcloud_topic"),
                "odom_topic": LaunchConfiguration("odom_topic"),
                "target_point_topic": LaunchConfiguration("target_point_topic"),
                "require_target_point": ParameterValue(
                    LaunchConfiguration("require_target_point"), value_type=bool
                ),
                "publish_rate_hz": ParameterValue(
                    LaunchConfiguration("e2e_publish_rate_hz"), value_type=float
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

    return LaunchDescription(
        [
            DeclareLaunchArgument("use_shadow_mode_bringup", default_value="true"),
            DeclareLaunchArgument("use_e2e_transfuser", default_value="true"),
            DeclareLaunchArgument("use_e2e_metrics", default_value="true"),
            DeclareLaunchArgument("use_adas_bringup", default_value="false"),
            DeclareLaunchArgument("virtual_input_mode", default_value="pointcloud"),
            DeclareLaunchArgument("lane_detection_scan_topic", default_value="/livox/lane_detection/scan"),
            DeclareLaunchArgument("pointcloud_topic", default_value="/livox/lidar"),
            DeclareLaunchArgument("odom_topic", default_value="/Odometry"),
            DeclareLaunchArgument("image_topic", default_value="/sensing/camera/camera0/image_rect_color"),
            DeclareLaunchArgument("camera_info_topic", default_value="/sensing/camera/camera0/camera_info"),
            DeclareLaunchArgument("target_point_topic", default_value="/shadow/route/target_point"),
            DeclareLaunchArgument("require_target_point", default_value="true"),
            DeclareLaunchArgument("record_shadow_bag", default_value="false"),
            DeclareLaunchArgument(
                "bag_record_regex",
                default_value="(/shadow/.*|/livox/lane_detection/.*|/Odometry|/scan)",
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
            DeclareLaunchArgument("e2e_runtime_mode", default_value="mock"),
            DeclareLaunchArgument("e2e_precision_mode", default_value="fp32"),
            DeclareLaunchArgument("e2e_model_variant", default_value="tfv6_resnet34"),
            DeclareLaunchArgument(
                "e2e_model_path",
                default_value="Data/models/tfv6/tfv6_resnet34",
            ),
            DeclareLaunchArgument("lead_project_root", default_value=""),
            DeclareLaunchArgument("e2e_publish_rate_hz", default_value="10.0"),
            DeclareLaunchArgument("e2e_metrics_publish_rate_hz", default_value="10.0"),
            DeclareLaunchArgument("input_timeout_sec", default_value="0.5"),
            shadow_mode,
            e2e_transfuser,
            e2e_metrics,
        ]
    )
