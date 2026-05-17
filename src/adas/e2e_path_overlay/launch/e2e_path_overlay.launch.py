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
                default_value="/yolo/tracking",
            ),
            DeclareLaunchArgument(
                "output_image_topic",
                default_value="/shadow/e2e/overlay_image",
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
                        "use_tf_translation": ParameterValue(
                            LaunchConfiguration("use_tf_translation"), value_type=bool
                        ),
                        "output_max_edge_px": ParameterValue(
                            LaunchConfiguration("output_max_edge_px"), value_type=int
                        ),
                    },
                ],
            ),
        ]
    )
