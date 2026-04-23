from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription(
        [
            Node(
                package="shadow_mode_virtual_control",
                executable="shadow_virtual_control_node",
                name="shadow_virtual_control",
                output="screen",
                parameters=[
                    {
                        "input_mode": "scan",
                        "input_scan_topic": "/livox/lane_detection/scan",
                        "input_pointcloud_topic": "/livox/lidar",
                        "output_frame": "",
                        "wheelbase": 2.7,
                        "lookahead_distance": 6.0,
                        "max_steering_rad": 0.6,
                        "forward_min_distance": 2.0,
                        "forward_max_distance": 20.0,
                        "bin_size": 1.0,
                        "max_lateral_distance": 8.0,
                        "assumed_lane_half_width": 1.75,
                        "min_points_per_side": 1,
                        "publish_debug_markers": True,
                        "warning_missing_boundary_weight": 0.7,
                        "warning_curvature_weight": 0.3,
                        "pointcloud_z_min": -1.5,
                        "pointcloud_z_max": 1.5,
                        "pointcloud_stride": 1,
                    }
                ],
            )
        ]
    )
