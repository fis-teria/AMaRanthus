import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (
    EnvironmentVariable,
    LaunchConfiguration,
    PathJoinSubstitution,
    PythonExpression,
)
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    camera_lidar_share = FindPackageShare("camera_lidar_bringup")
    livox_share = FindPackageShare("livox_ros_driver2")
    v4l2_share = FindPackageShare("v4l2_camera")

    source_dir = os.path.realpath(__file__)
    for _ in range(4):
        source_dir = os.path.dirname(source_dir)
    yolo_venv_site = os.path.join(
        source_dir,
        "img_proc",
        "yolo_ros",
        ".venv",
        "lib",
        "python3.10",
        "site-packages",
    )
    yolo_torch_lib = os.path.join(yolo_venv_site, "torch", "lib")

    use_v4l2_camera = LaunchConfiguration("use_v4l2_camera")
    use_livox_driver = LaunchConfiguration("use_livox_driver")
    use_livox_rviz = LaunchConfiguration("use_livox_rviz")
    use_yolo = LaunchConfiguration("use_yolo")

    livox_msg_condition = IfCondition(
        PythonExpression(
            ["'", use_livox_driver, "' == 'true' and '", use_livox_rviz, "' != 'true'"]
        )
    )
    livox_rviz_condition = IfCondition(
        PythonExpression(
            ["'", use_livox_driver, "' == 'true' and '", use_livox_rviz, "' == 'true'"]
        )
    )

    v4l2_camera_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([v4l2_share, "launch", "v4l2_camera.launch.py"])
        ),
        launch_arguments={
            "container": LaunchConfiguration("v4l2_container"),
            "image_topic": LaunchConfiguration("v4l2_image_topic"),
            "camera_name": LaunchConfiguration("v4l2_camera_name"),
            "v4l2_camera_namespace": LaunchConfiguration("v4l2_camera_namespace"),
            "v4l2_camera_param_path": LaunchConfiguration("v4l2_camera_param_path"),
            "rate_diagnostics_param_path": LaunchConfiguration(
                "rate_diagnostics_param_path"
            ),
            "camera_info_url": LaunchConfiguration("camera_info_url"),
            "use_intra_process": LaunchConfiguration("use_intra_process"),
            "use_sensor_data_qos": LaunchConfiguration("use_sensor_data_qos"),
            "publish_rate": LaunchConfiguration("camera_publish_rate"),
            "use_v4l2_buffer_timestamps": LaunchConfiguration(
                "use_v4l2_buffer_timestamps"
            ),
            "use_image_transport": LaunchConfiguration("use_image_transport"),
            "hardware_id": LaunchConfiguration("camera_hardware_id"),
        }.items(),
        condition=IfCondition(use_v4l2_camera),
    )

    livox_msg_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([livox_share, "launch_ROS2", "msg_HAP_launch.py"])
        ),
        condition=livox_msg_condition,
    )

    livox_rviz_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([livox_share, "launch_ROS2", "rviz_HAP_launch.py"])
        ),
        condition=livox_rviz_condition,
    )

    yolo_env = {
        "PYTHONPATH": [
            LaunchConfiguration("yolo_python_site"),
            ":",
            EnvironmentVariable("PYTHONPATH", default_value=""),
        ],
        "LD_LIBRARY_PATH": [
            LaunchConfiguration("yolo_torch_lib"),
            ":",
            EnvironmentVariable("LD_LIBRARY_PATH", default_value=""),
        ],
    }
    yolo_params = {
        "model_type": "YOLO",
        "model": LaunchConfiguration("yolo_model"),
        "device": LaunchConfiguration("yolo_device"),
        "fuse_model": False,
        "yolo_encoding": LaunchConfiguration("yolo_encoding"),
        "enable": ParameterValue(LaunchConfiguration("yolo_enable"), value_type=bool),
        "threshold": ParameterValue(
            LaunchConfiguration("yolo_threshold"), value_type=float
        ),
        "iou": ParameterValue(LaunchConfiguration("yolo_iou"), value_type=float),
        "imgsz_height": ParameterValue(
            LaunchConfiguration("yolo_imgsz_height"), value_type=int
        ),
        "imgsz_width": ParameterValue(
            LaunchConfiguration("yolo_imgsz_width"), value_type=int
        ),
        "half": False,
        "max_det": 300,
        "augment": False,
        "agnostic_nms": False,
        "retina_masks": False,
        "image_reliability": ParameterValue(
            LaunchConfiguration("yolo_image_reliability"), value_type=int
        ),
    }

    yolo_node = Node(
        package="yolo_ros",
        executable="yolo_node",
        name="yolo_node",
        namespace=LaunchConfiguration("yolo_namespace"),
        output="screen",
        parameters=[yolo_params],
        remappings=[("image_raw", LaunchConfiguration("yolo_input_image_topic"))],
        additional_env=yolo_env,
        condition=IfCondition(use_yolo),
    )
    tracking_node = Node(
        package="yolo_ros",
        executable="tracking_node",
        name="tracking_node",
        namespace=LaunchConfiguration("yolo_namespace"),
        output="screen",
        parameters=[
            {
                "tracker": LaunchConfiguration("yolo_tracker"),
                "image_reliability": ParameterValue(
                    LaunchConfiguration("yolo_image_reliability"), value_type=int
                ),
            }
        ],
        remappings=[("image_raw", LaunchConfiguration("yolo_input_image_topic"))],
        additional_env=yolo_env,
        condition=IfCondition(
            PythonExpression(
                [
                    "'",
                    use_yolo,
                    "'.lower() == 'true' and '",
                    LaunchConfiguration("yolo_use_tracking"),
                    "'.lower() == 'true'",
                ]
            )
        ),
    )
    debug_tracking_node = Node(
        package="yolo_ros",
        executable="debug_node",
        name="debug_node",
        namespace=LaunchConfiguration("yolo_namespace"),
        output="screen",
        parameters=[
            {
                "image_reliability": ParameterValue(
                    LaunchConfiguration("yolo_image_reliability"), value_type=int
                )
            }
        ],
        remappings=[
            ("image_raw", LaunchConfiguration("yolo_input_image_topic")),
            ("detections", "tracking"),
        ],
        additional_env=yolo_env,
        condition=IfCondition(
            PythonExpression(
                [
                    "'",
                    use_yolo,
                    "'.lower() == 'true' and '",
                    LaunchConfiguration("yolo_use_debug"),
                    "'.lower() == 'true' and '",
                    LaunchConfiguration("yolo_use_tracking"),
                    "'.lower() == 'true'",
                ]
            )
        ),
    )
    debug_detections_node = Node(
        package="yolo_ros",
        executable="debug_node",
        name="debug_node",
        namespace=LaunchConfiguration("yolo_namespace"),
        output="screen",
        parameters=[
            {
                "image_reliability": ParameterValue(
                    LaunchConfiguration("yolo_image_reliability"), value_type=int
                )
            }
        ],
        remappings=[
            ("image_raw", LaunchConfiguration("yolo_input_image_topic")),
            ("detections", "detections"),
        ],
        additional_env=yolo_env,
        condition=IfCondition(
            PythonExpression(
                [
                    "'",
                    use_yolo,
                    "'.lower() == 'true' and '",
                    LaunchConfiguration("yolo_use_debug"),
                    "'.lower() == 'true' and '",
                    LaunchConfiguration("yolo_use_tracking"),
                    "'.lower() != 'true'",
                ]
            )
        ),
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("use_v4l2_camera", default_value="true"),
            DeclareLaunchArgument("use_livox_driver", default_value="true"),
            DeclareLaunchArgument("use_livox_rviz", default_value="false"),
            DeclareLaunchArgument("use_yolo", default_value="false"),
            DeclareLaunchArgument("v4l2_container", default_value=""),
            DeclareLaunchArgument("v4l2_image_topic", default_value="image_rect_color"),
            DeclareLaunchArgument("v4l2_camera_name", default_value="camera0"),
            DeclareLaunchArgument("v4l2_camera_namespace", default_value="/sensing/camera"),
            DeclareLaunchArgument(
                "v4l2_camera_param_path",
                default_value=PathJoinSubstitution(
                    [camera_lidar_share, "config", "tier4_c2_v4l2_camera.param.yaml"]
                ),
            ),
            DeclareLaunchArgument(
                "rate_diagnostics_param_path",
                default_value=PathJoinSubstitution(
                    [camera_lidar_share, "config", "rate_diagnostics.param.yaml"]
                ),
            ),
            DeclareLaunchArgument("camera_info_url", default_value=""),
            DeclareLaunchArgument("use_intra_process", default_value="false"),
            DeclareLaunchArgument("use_sensor_data_qos", default_value="true"),
            DeclareLaunchArgument("camera_publish_rate", default_value="-1.0"),
            DeclareLaunchArgument("use_v4l2_buffer_timestamps", default_value="true"),
            DeclareLaunchArgument("use_image_transport", default_value="true"),
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
            DeclareLaunchArgument("yolo_python_site", default_value=yolo_venv_site),
            DeclareLaunchArgument("yolo_torch_lib", default_value=yolo_torch_lib),
            v4l2_camera_launch,
            livox_msg_launch,
            livox_rviz_launch,
            yolo_node,
            tracking_node,
            debug_tracking_node,
            debug_detections_node,
        ]
    )
