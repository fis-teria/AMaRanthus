from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    package_share = FindPackageShare("e2e_path_overlay")
    param_file = LaunchConfiguration("param_file")

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "param_file",
                default_value=PathJoinSubstitution(
                    [package_share, "config", "e2e_path_overlay.param.yaml"]
                ),
            ),
            DeclareLaunchArgument(
                "image_topic",
                default_value="/sensing/camera/camera0/image_rect_color",
            ),
            DeclareLaunchArgument(
                "camera_info_topic",
                default_value="/sensing/camera/camera0/camera_info",
            ),
            DeclareLaunchArgument("path_topic", default_value="/shadow/e2e/path"),
            DeclareLaunchArgument(
                "yolo_detections_topic",
                default_value="/yolo/detections",
            ),
            DeclareLaunchArgument(
                "output_image_topic",
                default_value="/shadow/e2e/overlay_image",
            ),
            DeclareLaunchArgument(
                "output_compressed_image_topic",
                default_value="/shadow/e2e/overlay_image/compressed",
            ),
            DeclareLaunchArgument("output_compressed_jpeg_quality", default_value="80"),
            DeclareLaunchArgument(
                "model_input_image_topic",
                default_value="/shadow/e2e/model_input_image",
            ),
            DeclareLaunchArgument(
                "use_tf_translation",
                default_value="true",
            ),
            DeclareLaunchArgument(
                "executable",
                default_value="e2e_path_overlay_node",
            ),
            DeclareLaunchArgument(
                "output_max_edge_px",
                default_value="640",
            ),
            DeclareLaunchArgument("process_rate_hz", default_value="10.0"),
            DeclareLaunchArgument("stale_image_timeout_sec", default_value="0.5"),
            DeclareLaunchArgument("model_input_width_px", default_value="1152"),
            DeclareLaunchArgument("model_input_height_px", default_value="384"),
            Node(
                package="e2e_path_overlay",
                executable=LaunchConfiguration("executable"),
                name="e2e_path_overlay",
                output="screen",
                parameters=[
                    param_file,
                    {
                        "image_topic": LaunchConfiguration("image_topic"),
                        "camera_info_topic": LaunchConfiguration("camera_info_topic"),
                        "path_topic": LaunchConfiguration("path_topic"),
                        "yolo_detections_topic": LaunchConfiguration(
                            "yolo_detections_topic"
                        ),
                        "output_image_topic": LaunchConfiguration("output_image_topic"),
                        "output_compressed_image_topic": LaunchConfiguration(
                            "output_compressed_image_topic"
                        ),
                        "output_compressed_jpeg_quality": ParameterValue(
                            LaunchConfiguration("output_compressed_jpeg_quality"),
                            value_type=int,
                        ),
                        "model_input_image_topic": LaunchConfiguration(
                            "model_input_image_topic"
                        ),
                        "use_tf_translation": ParameterValue(
                            LaunchConfiguration("use_tf_translation"), value_type=bool
                        ),
                        "output_max_edge_px": ParameterValue(
                            LaunchConfiguration("output_max_edge_px"), value_type=int
                        ),
                        "process_rate_hz": ParameterValue(
                            LaunchConfiguration("process_rate_hz"), value_type=float
                        ),
                        "stale_image_timeout_sec": ParameterValue(
                            LaunchConfiguration("stale_image_timeout_sec"),
                            value_type=float,
                        ),
                        "model_input_width_px": ParameterValue(
                            LaunchConfiguration("model_input_width_px"), value_type=int
                        ),
                        "model_input_height_px": ParameterValue(
                            LaunchConfiguration("model_input_height_px"), value_type=int
                        ),
                    },
                ],
            ),
        ]
    )
