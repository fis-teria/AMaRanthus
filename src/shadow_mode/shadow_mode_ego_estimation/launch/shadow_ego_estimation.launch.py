from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription(
        [
            Node(
                package="shadow_mode_ego_estimation",
                executable="shadow_ego_estimation_node",
                name="shadow_ego_estimation",
                output="screen",
                parameters=[
                    {
                        "input_odom_topic": "/Odometry",
                        "output_frame": "",
                        "path_buffer_size": 200,
                        "min_dt": 0.01,
                        "min_speed_for_curvature": 0.5,
                        "speed_smoothing_gain": 0.2,
                        "yaw_rate_smoothing_gain": 0.2,
                        "publish_debug_markers": True,
                    }
                ],
            )
        ]
    )
