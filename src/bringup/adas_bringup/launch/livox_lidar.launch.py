from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    use_rviz = LaunchConfiguration("use_rviz")
    xfer_format = LaunchConfiguration("xfer_format")
    multi_topic = LaunchConfiguration("multi_topic")
    data_src = LaunchConfiguration("data_src")
    publish_freq = LaunchConfiguration("publish_freq")
    output_data_type = LaunchConfiguration("output_data_type")
    frame_id = LaunchConfiguration("frame_id")
    lvx_file_path = LaunchConfiguration("lvx_file_path")
    user_config_path = LaunchConfiguration("user_config_path")
    cmdline_input_bd_code = LaunchConfiguration("cmdline_input_bd_code")
    rviz_config_path = LaunchConfiguration("rviz_config_path")
    record_bag = LaunchConfiguration("record_bag")
    bag_output = LaunchConfiguration("bag_output")
    bag_record_regex = LaunchConfiguration("bag_record_regex")

    livox_driver = Node(
        package="livox_ros_driver2",
        executable="livox_ros_driver2_node",
        name="livox_lidar_publisher",
        output="screen",
        parameters=[
            {
                "xfer_format": xfer_format,
                "multi_topic": multi_topic,
                "data_src": data_src,
                "publish_freq": publish_freq,
                "output_data_type": output_data_type,
                "frame_id": frame_id,
                "lvx_file_path": lvx_file_path,
                "user_config_path": user_config_path,
                "cmdline_input_bd_code": cmdline_input_bd_code,
            }
        ],
    )

    rviz = Node(
        package="rviz2",
        executable="rviz2",
        name="rviz2",
        output="screen",
        arguments=["--display-config", rviz_config_path],
        condition=IfCondition(use_rviz),
    )

    rosbag_record = ExecuteProcess(
        cmd=[
            "bash",
            "-lc",
            (
                'base="$1"; regex="$2"; '
                'mkdir -p "$(dirname "$base")"; '
                'output="$base"; '
                'index=1; '
                'while [ -e "$output" ]; do '
                'output="${base}_$index"; '
                'index=$((index + 1)); '
                "done; "
                'echo "rosbag2 output: $output"; '
                'exec ros2 bag record --output "$output" --regex "$regex"'
            ),
            "--",
            bag_output,
            bag_record_regex,
        ],
        name="livox_sensor_bag_record",
        output="screen",
        condition=IfCondition(record_bag),
    )

    livox_share = FindPackageShare("livox_ros_driver2")

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "use_rviz",
                default_value="true",
                description="true のとき RViz も一緒に起動します。",
            ),
            DeclareLaunchArgument(
                "xfer_format",
                default_value="0",
                description=(
                    "点群形式。0: Livox PointCloud2(PointXYZRTLT)、"
                    "1: Livox CustomMsg"
                ),
            ),
            DeclareLaunchArgument(
                "multi_topic",
                default_value="0",
                description="0: 全 LiDAR 共通トピック、1: LiDAR ごとの個別トピック",
            ),
            DeclareLaunchArgument(
                "data_src",
                default_value="0",
                description="データ取得元。0 は実機 LiDAR です。",
            ),
            DeclareLaunchArgument(
                "publish_freq",
                default_value="10.0",
                description="点群 publish 周波数 [Hz]",
            ),
            DeclareLaunchArgument(
                "output_data_type",
                default_value="0",
                description="Livox driver の出力データ種別設定",
            ),
            DeclareLaunchArgument(
                "frame_id",
                default_value="livox_frame",
                description="出力メッセージに設定する frame_id",
            ),
            DeclareLaunchArgument(
                "lvx_file_path",
                default_value="/home/livox/livox_test.lvx",
                description="LVX ファイル再生時の入力ファイルパス",
            ),
            DeclareLaunchArgument(
                "user_config_path",
                default_value=PathJoinSubstitution(
                    [livox_share, "config", "HAP_config.json"]
                ),
                description="Livox driver が使用する JSON 設定ファイル",
            ),
            DeclareLaunchArgument(
                "cmdline_input_bd_code",
                default_value="livox0000000001",
                description="接続対象 LiDAR の broadcast code",
            ),
            DeclareLaunchArgument(
                "rviz_config_path",
                default_value=PathJoinSubstitution(
                    [livox_share, "config", "display_point_cloud_ROS2.rviz"]
                ),
                description="RViz の設定ファイルパス",
            ),
            DeclareLaunchArgument(
                "record_bag",
                default_value="false",
                description="true のとき rosbag2 で LiDAR センサトピックを記録します。",
            ),
            DeclareLaunchArgument(
                "bag_output",
                default_value=PathJoinSubstitution(
                    ["Data", "rosbag", "livox_sensor_bag"]
                ),
                description="rosbag2 の保存先ディレクトリ名。既定では Data/rosbag 配下に保存します。",
            ),
            DeclareLaunchArgument(
                "bag_record_regex",
                default_value="livox",
                description=(
                    "rosbag2 で記録するトピック regex。"
                    "/livox/lidar, /livox/imu と multi_topic 時の派生名を対象にします。"
                ),
            ),
            livox_driver,
            rviz,
            rosbag_record,
        ]
    )
