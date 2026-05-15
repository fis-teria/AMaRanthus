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
    camera_lidar_bringup_share = FindPackageShare("camera_lidar_bringup")
    e2e_path_overlay_share = FindPackageShare("e2e_path_overlay")

    use_camera_lidar_bringup = LaunchConfiguration("use_camera_lidar_bringup")
    use_shadow_mode_bringup = LaunchConfiguration("use_shadow_mode_bringup")
    use_e2e_transfuser = LaunchConfiguration("use_e2e_transfuser")
    use_e2e_metrics = LaunchConfiguration("use_e2e_metrics")
    use_e2e_path_overlay = LaunchConfiguration("use_e2e_path_overlay")

    e2e_param_file = LaunchConfiguration("e2e_param_file")
    e2e_metrics_param_file = LaunchConfiguration("e2e_metrics_param_file")
    e2e_path_overlay_param_file = LaunchConfiguration("e2e_path_overlay_param_file")

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

    camera_lidar_bringup = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution(
                [
                    camera_lidar_bringup_share,
                    "launch",
                    "camera_lidar_bringup.launch.py",
                ]
            )
        ),
        launch_arguments={
            "use_v4l2_camera": LaunchConfiguration("use_v4l2_camera"),
            "use_livox_driver": LaunchConfiguration("use_livox_driver"),
            "use_livox_rviz": LaunchConfiguration("use_livox_rviz"),
            "use_yolo": LaunchConfiguration("use_yolo"),
            "v4l2_image_topic": LaunchConfiguration("v4l2_image_topic"),
            "v4l2_camera_name": LaunchConfiguration("v4l2_camera_name"),
            "v4l2_camera_namespace": LaunchConfiguration("v4l2_camera_namespace"),
            "v4l2_camera_param_path": LaunchConfiguration("v4l2_camera_param_path"),
            "rate_diagnostics_param_path": LaunchConfiguration(
                "rate_diagnostics_param_path"
            ),
            "camera_info_url": LaunchConfiguration("camera_info_url"),
            "use_sensor_data_qos": LaunchConfiguration("use_sensor_data_qos"),
            "camera_publish_rate": LaunchConfiguration("camera_publish_rate"),
            "camera_hardware_id": LaunchConfiguration("camera_hardware_id"),
            "yolo_model": LaunchConfiguration("yolo_model"),
            "yolo_device": LaunchConfiguration("yolo_device"),
            "yolo_enable": LaunchConfiguration("yolo_enable"),
            "yolo_threshold": LaunchConfiguration("yolo_threshold"),
            "yolo_iou": LaunchConfiguration("yolo_iou"),
            "yolo_encoding": LaunchConfiguration("yolo_encoding"),
            "yolo_tracker": LaunchConfiguration("yolo_tracker"),
            "yolo_imgsz_height": LaunchConfiguration("yolo_imgsz_height"),
            "yolo_imgsz_width": LaunchConfiguration("yolo_imgsz_width"),
            "yolo_input_image_topic": LaunchConfiguration("yolo_input_image_topic"),
            "yolo_image_reliability": LaunchConfiguration("yolo_image_reliability"),
            "yolo_namespace": LaunchConfiguration("yolo_namespace"),
            "yolo_use_tracking": LaunchConfiguration("yolo_use_tracking"),
            "yolo_use_debug": LaunchConfiguration("yolo_use_debug"),
        }.items(),
        condition=IfCondition(use_camera_lidar_bringup),
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

    e2e_path_overlay = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution(
                [
                    e2e_path_overlay_share,
                    "launch",
                    "e2e_path_overlay.launch.py",
                ]
            )
        ),
        launch_arguments={
            "param_file": e2e_path_overlay_param_file,
            "image_topic": LaunchConfiguration("image_topic"),
            "camera_info_topic": LaunchConfiguration("camera_info_topic"),
            "path_topic": LaunchConfiguration("e2e_path_topic"),
            "output_image_topic": LaunchConfiguration("e2e_overlay_image_topic"),
            "use_tf_translation": LaunchConfiguration("e2e_overlay_use_tf_translation"),
        }.items(),
        condition=IfCondition(use_e2e_path_overlay),
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("use_camera_lidar_bringup", default_value="true"),
            DeclareLaunchArgument("use_shadow_mode_bringup", default_value="true"),
            DeclareLaunchArgument("use_e2e_transfuser", default_value="true"),
            DeclareLaunchArgument("use_e2e_metrics", default_value="true"),
            DeclareLaunchArgument("use_e2e_path_overlay", default_value="true"),
            DeclareLaunchArgument("use_v4l2_camera", default_value="true"),
            DeclareLaunchArgument("use_livox_driver", default_value="true"),
            DeclareLaunchArgument("use_livox_rviz", default_value="false"),
            DeclareLaunchArgument("use_yolo", default_value="false"),
            DeclareLaunchArgument("use_adas_bringup", default_value="false"),
            DeclareLaunchArgument("virtual_input_mode", default_value="pointcloud"),
            DeclareLaunchArgument("lane_detection_scan_topic", default_value="/livox/lane_detection/scan"),
            DeclareLaunchArgument("pointcloud_topic", default_value="/livox/lidar"),
            DeclareLaunchArgument("odom_topic", default_value="/Odometry"),
            DeclareLaunchArgument("image_topic", default_value="/sensing/camera/camera0/image_rect_color"),
            DeclareLaunchArgument("camera_info_topic", default_value="/sensing/camera/camera0/camera_info"),
            DeclareLaunchArgument("v4l2_image_topic", default_value="image_rect_color"),
            DeclareLaunchArgument("v4l2_camera_name", default_value="camera0"),
            DeclareLaunchArgument("v4l2_camera_namespace", default_value="/sensing/camera"),
            DeclareLaunchArgument(
                "v4l2_camera_param_path",
                default_value=PathJoinSubstitution(
                    [
                        camera_lidar_bringup_share,
                        "config",
                        "tier4_c2_v4l2_camera.param.yaml",
                    ]
                ),
            ),
            DeclareLaunchArgument(
                "rate_diagnostics_param_path",
                default_value=PathJoinSubstitution(
                    [
                        camera_lidar_bringup_share,
                        "config",
                        "rate_diagnostics.param.yaml",
                    ]
                ),
            ),
            DeclareLaunchArgument("camera_info_url", default_value=""),
            DeclareLaunchArgument("use_sensor_data_qos", default_value="true"),
            DeclareLaunchArgument("camera_publish_rate", default_value="-1.0"),
            DeclareLaunchArgument(
                "camera_hardware_id",
                default_value="tier4_automotive_hdr_camera_c2",
            ),
            DeclareLaunchArgument("yolo_model", default_value="yolo11n.pt"),
            DeclareLaunchArgument("yolo_device", default_value="cpu"),
            DeclareLaunchArgument("yolo_enable", default_value="true"),
            DeclareLaunchArgument("yolo_threshold", default_value="0.5"),
            DeclareLaunchArgument("yolo_iou", default_value="0.7"),
            DeclareLaunchArgument("yolo_encoding", default_value="bgr8"),
            DeclareLaunchArgument("yolo_tracker", default_value="bytetrack.yaml"),
            DeclareLaunchArgument("yolo_imgsz_height", default_value="640"),
            DeclareLaunchArgument("yolo_imgsz_width", default_value="640"),
            DeclareLaunchArgument(
                "yolo_input_image_topic",
                default_value="/sensing/camera/camera0/image_rect_color",
            ),
            DeclareLaunchArgument("yolo_image_reliability", default_value="2"),
            DeclareLaunchArgument("yolo_namespace", default_value="yolo"),
            DeclareLaunchArgument("yolo_use_tracking", default_value="true"),
            DeclareLaunchArgument("yolo_use_debug", default_value="true"),
            DeclareLaunchArgument("target_point_topic", default_value="/shadow/route/target_point"),
            DeclareLaunchArgument("e2e_path_topic", default_value="/shadow/e2e/path"),
            DeclareLaunchArgument(
                "e2e_overlay_image_topic",
                default_value="/shadow/e2e/overlay_image",
            ),
            DeclareLaunchArgument("e2e_overlay_use_tf_translation", default_value="true"),
            DeclareLaunchArgument("require_target_point", default_value="true"),
            DeclareLaunchArgument("record_shadow_bag", default_value="false"),
            DeclareLaunchArgument(
                "bag_record_regex",
                default_value="(/shadow/.*|/livox/lane_detection/.*|/yolo/.*|/Odometry|/scan)",
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
            DeclareLaunchArgument(
                "e2e_path_overlay_param_file",
                default_value=PathJoinSubstitution(
                    [e2e_path_overlay_share, "config", "e2e_path_overlay.param.yaml"]
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
            camera_lidar_bringup,
            shadow_mode,
            e2e_transfuser,
            e2e_metrics,
            e2e_path_overlay,
        ]
    )
