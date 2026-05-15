import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    description_share = get_package_share_directory("adas_description")
    default_urdf_path = os.path.join(description_share, "urdf", "adas_livox.urdf")

    robot_description_path = LaunchConfiguration("robot_description_path")
    use_sim_time = LaunchConfiguration("use_sim_time")

    robot_state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        name="adas_robot_state_publisher",
        output="screen",
        parameters=[
            {
                "robot_description": ParameterValue(
                    Command(["cat ", robot_description_path]),
                    value_type=str,
                ),
                "use_sim_time": use_sim_time,
            }
        ],
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "robot_description_path",
                default_value=default_urdf_path,
                description="URDF path for the ADAS sensor TF tree.",
            ),
            DeclareLaunchArgument("use_sim_time", default_value="false"),
            robot_state_publisher,
        ]
    )
