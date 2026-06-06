from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    share = FindPackageShare("camera_lane_detection")
    param_file = LaunchConfiguration("param_file")

    node = Node(
        package="camera_lane_detection",
        executable="camera_lane_detection_node.py",
        name="camera_lane_detection",
        output="screen",
        parameters=[
            param_file,
            {
                "enabled": ParameterValue(LaunchConfiguration("enabled"), value_type=bool),
                "backend": LaunchConfiguration("backend"),
                "model_path": LaunchConfiguration("model_path"),
                "image_topic": LaunchConfiguration("camera_lane_detection_image_topic"),
                "camera_info_topic": LaunchConfiguration("camera_lane_detection_camera_info_topic"),
                "output_path_topic": LaunchConfiguration("output_path_topic"),
                "status_topic": LaunchConfiguration("status_topic"),
                "debug_mask_topic": LaunchConfiguration("debug_mask_topic"),
                "debug_image_topic": LaunchConfiguration("debug_image_topic"),
                "output_frame": LaunchConfiguration("output_frame"),
                "max_process_rate_hz": ParameterValue(
                    LaunchConfiguration("max_process_rate_hz"), value_type=float
                ),
                "input_width": ParameterValue(
                    LaunchConfiguration("input_width"), value_type=int
                ),
                "input_height": ParameterValue(
                    LaunchConfiguration("input_height"), value_type=int
                ),
                "publish_debug_images": ParameterValue(
                    LaunchConfiguration("publish_debug_images"), value_type=bool
                ),
                "min_lane_confidence": ParameterValue(
                    LaunchConfiguration("min_lane_confidence"), value_type=float
                ),
                "smoothing_alpha": ParameterValue(
                    LaunchConfiguration("smoothing_alpha"), value_type=float
                ),
                "roi_top_ratio": ParameterValue(
                    LaunchConfiguration("roi_top_ratio"), value_type=float
                ),
            },
        ],
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "param_file",
                default_value=PathJoinSubstitution(
                    [share, "config", "camera_lane_detection.param.yaml"]
                ),
            ),
            DeclareLaunchArgument("enabled", default_value="true"),
            DeclareLaunchArgument("backend", default_value="opencv_classical"),
            DeclareLaunchArgument("model_path", default_value=""),
            DeclareLaunchArgument(
                "camera_lane_detection_image_topic",
                default_value="/sensing/camera/camera0/image_rect_color",
            ),
            DeclareLaunchArgument(
                "camera_lane_detection_camera_info_topic",
                default_value="/sensing/camera/camera0/camera_info",
            ),
            DeclareLaunchArgument(
                "output_path_topic", default_value="/shadow/perception/lane_path"
            ),
            DeclareLaunchArgument("status_topic", default_value="/shadow/perception/lane_status"),
            DeclareLaunchArgument("debug_mask_topic", default_value="/shadow/perception/lane_mask"),
            DeclareLaunchArgument(
                "debug_image_topic", default_value="/shadow/perception/lane_debug_image"
            ),
            DeclareLaunchArgument("output_frame", default_value="base_link"),
            DeclareLaunchArgument("max_process_rate_hz", default_value="20.0"),
            DeclareLaunchArgument("input_width", default_value="512"),
            DeclareLaunchArgument("input_height", default_value="288"),
            DeclareLaunchArgument("publish_debug_images", default_value="false"),
            DeclareLaunchArgument("min_lane_confidence", default_value="0.25"),
            DeclareLaunchArgument("smoothing_alpha", default_value="0.35"),
            DeclareLaunchArgument("roi_top_ratio", default_value="0.45"),
            node,
        ]
    )
