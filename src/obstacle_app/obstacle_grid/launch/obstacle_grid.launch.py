import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node
import launch

################### user configure parameters for ros2 start ###################
xfer_format   = 1    # 0-Pointcloud2(PointXYZRTL), 1-customized pointcloud format
multi_topic   = 0    # 0-All LiDARs share the same topic, 1-One LiDAR one topic
data_src      = 0    # 0-lidar, others-Invalid data src
publish_freq  = 10.0 # freqency of publish, 5.0, 10.0, 20.0, 50.0, etc.
output_type   = 0
frame_id      = 'livox_frame'
lvx_file_path = '/home/livox/livox_test.lvx'
cmdline_bd_code = 'livox0000000001'

cur_path = os.path.split(os.path.realpath(__file__))[0] + '/'
cur_config_path = cur_path + '../config'
rviz_config_path = os.path.join(cur_config_path, 'livox_lidar.rviz')
user_config_path = os.path.join(cur_config_path, 'HAP_config.json')
################### user configure parameters for ros2 end #####################

livox_ros2_params = [
    {"xfer_format": xfer_format},
    {"multi_topic": multi_topic},
    {"data_src": data_src},
    {"publish_freq": publish_freq},
    {"output_data_type": output_type},
    {"frame_id": frame_id},
    {"lvx_file_path": lvx_file_path},
    {"user_config_path": user_config_path},
    {"cmdline_input_bd_code": cmdline_bd_code}
]

def generate_launch_description():
    grid_node = Node(
        package='obstacle_grid',
        executable='obstacle_grid_node',
        name='obstacle_grid_node',
        output='screen',
        parameters=[{
            'points_topic': '/livox/lidar',
            'output_frame': 'base_link',
            'grid_resolution': 0.1,
            'grid_width_cells': 200,
            'grid_height_cells': 200,
            'origin_x': -10.0,
            'origin_y': -10.0,
            'z_min': 0.05,
            'z_max': 2.0,
            'obstacle_min_height': 0.10,
            'min_points_per_cell': 2,
            'publish_markers': True
        }]
    )

    livox_driver = Node(
    package='livox_ros_driver2',
    executable='livox_ros_driver2_node',
    name='livox_lidar_publisher',
    output='screen',
    parameters=livox_ros2_params
    )

    return LaunchDescription([livox_driver, grid_node])
