from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    use_adas_bringup = LaunchConfiguration("use_adas_bringup")
    use_livox_rviz = LaunchConfiguration("use_livox_rviz")
    use_ego_estimation = LaunchConfiguration("use_ego_estimation")
    use_virtual_control = LaunchConfiguration("use_virtual_control")
    use_metrics = LaunchConfiguration("use_metrics")
    record_shadow_bag = LaunchConfiguration("record_shadow_bag")

    pointcloud_topic = LaunchConfiguration("pointcloud_topic")
    scan_topic = LaunchConfiguration("scan_topic")
    virtual_input_mode = LaunchConfiguration("virtual_input_mode")
    virtual_pointcloud_topic = LaunchConfiguration("virtual_pointcloud_topic")
    pointcloud_z_min = LaunchConfiguration("pointcloud_z_min")
    pointcloud_z_max = LaunchConfiguration("pointcloud_z_max")
    pointcloud_stride = LaunchConfiguration("pointcloud_stride")
    odom_topic = LaunchConfiguration("odom_topic")
    ego_output_frame = LaunchConfiguration("ego_output_frame")
    virtual_output_frame = LaunchConfiguration("virtual_output_frame")

    shadow_mode_param_file = LaunchConfiguration("shadow_mode_param_file")
    pointcloud_to_laserscan_param_file = LaunchConfiguration(
        "pointcloud_to_laserscan_param_file"
    )
    lane_detection_model_path = LaunchConfiguration("lane_detection_model_path")
    lane_detection_colored_cloud_topic = LaunchConfiguration(
        "lane_detection_colored_cloud_topic"
    )
    lane_detection_scan_topic = LaunchConfiguration("lane_detection_scan_topic")
    lane_detection_objects_topic = LaunchConfiguration("lane_detection_objects_topic")
    lane_detection_output_frame = LaunchConfiguration("lane_detection_output_frame")

    bag_output = LaunchConfiguration("bag_output")
    bag_record_regex = LaunchConfiguration("bag_record_regex")
    metrics_csv_logging = LaunchConfiguration("metrics_csv_logging")
    metrics_csv_path = LaunchConfiguration("metrics_csv_path")

    shadow_bringup_share = FindPackageShare("shadow_mode_bringup")
    adas_bringup_share = FindPackageShare("adas_bringup")
    livox_lane_detection_share = FindPackageShare("livox_lane_detection")

    adas_pipeline = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution(
                [adas_bringup_share, "launch", "adas_bringup.launch.py"]
            )
        ),
        launch_arguments={
            "use_livox_rviz": use_livox_rviz,
            "pointcloud_topic": pointcloud_topic,
            "scan_topic": scan_topic,
            "pointcloud_to_laserscan_param_file": pointcloud_to_laserscan_param_file,
            "lane_detection_model_path": lane_detection_model_path,
            "lane_detection_colored_cloud_topic": lane_detection_colored_cloud_topic,
            "lane_detection_scan_topic": lane_detection_scan_topic,
            "lane_detection_objects_topic": lane_detection_objects_topic,
            "lane_detection_output_frame": lane_detection_output_frame,
        }.items(),
        condition=IfCondition(use_adas_bringup),
    )

    ego_estimation = Node(
        package="shadow_mode_ego_estimation",
        executable="shadow_ego_estimation_node",
        name="shadow_ego_estimation",
        output="screen",
        parameters=[
            shadow_mode_param_file,
            {
                "input_odom_topic": odom_topic,
                "output_frame": ego_output_frame,
            },
        ],
        condition=IfCondition(use_ego_estimation),
    )

    virtual_control = Node(
        package="shadow_mode_virtual_control",
        executable="shadow_virtual_control_node",
        name="shadow_virtual_control",
        output="screen",
        parameters=[
            shadow_mode_param_file,
            {
                "input_mode": virtual_input_mode,
                "input_scan_topic": lane_detection_scan_topic,
                "input_pointcloud_topic": virtual_pointcloud_topic,
                "output_frame": virtual_output_frame,
                "pointcloud_z_min": ParameterValue(pointcloud_z_min, value_type=float),
                "pointcloud_z_max": ParameterValue(pointcloud_z_max, value_type=float),
                "pointcloud_stride": ParameterValue(pointcloud_stride, value_type=int),
            },
        ],
        condition=IfCondition(use_virtual_control),
    )

    metrics = Node(
        package="shadow_mode_metrics",
        executable="shadow_mode_metrics_node",
        name="shadow_mode_metrics",
        output="screen",
        parameters=[
            shadow_mode_param_file,
            {
                "enable_csv_logging": ParameterValue(
                    metrics_csv_logging,
                    value_type=bool,
                ),
                "csv_path": metrics_csv_path,
            },
        ],
        condition=IfCondition(use_metrics),
    )

    shadow_bag_record = ExecuteProcess(
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
                'echo "shadow-mode rosbag2 output: $output"; '
                'exec ros2 bag record --output "$output" --regex "$regex"'
            ),
            "--",
            bag_output,
            bag_record_regex,
        ],
        name="shadow_mode_bag_record",
        output="screen",
        condition=IfCondition(record_shadow_bag),
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "use_adas_bringup",
                default_value="true",
                description=(
                    "true のとき Livox ADAS 前段 "
                    "(livox driver, lane detection, pointcloud_to_laserscan) も起動します。"
                ),
            ),
            DeclareLaunchArgument(
                "use_livox_rviz",
                default_value="false",
                description="ADAS 前段を起動する場合に Livox RViz launch を使うかどうか。",
            ),
            DeclareLaunchArgument(
                "use_ego_estimation",
                default_value="true",
                description="shadow_mode_ego_estimation を起動します。",
            ),
            DeclareLaunchArgument(
                "use_virtual_control",
                default_value="true",
                description="shadow_mode_virtual_control を起動します。",
            ),
            DeclareLaunchArgument(
                "use_metrics",
                default_value="true",
                description="shadow_mode_metrics を起動して ego と virtual control を比較します。",
            ),
            DeclareLaunchArgument(
                "shadow_mode_param_file",
                default_value=PathJoinSubstitution(
                    [shadow_bringup_share, "config", "shadow_mode_bringup.param.yaml"]
                ),
                description="Shadow-mode ノード群の共通パラメータファイル。",
            ),
            DeclareLaunchArgument(
                "pointcloud_topic",
                default_value="/livox/lidar",
                description="Livox PointCloud2 入力トピック。",
            ),
            DeclareLaunchArgument(
                "scan_topic",
                default_value="/scan",
                description="汎用 pointcloud_to_laserscan の出力 LaserScan トピック。",
            ),
            DeclareLaunchArgument(
                "virtual_input_mode",
                default_value="scan",
                description=(
                    "shadow_virtual_control の入力種別。"
                    "scan または pointcloud を指定します。"
                ),
            ),
            DeclareLaunchArgument(
                "virtual_pointcloud_topic",
                default_value="/livox/lidar",
                description="virtual_input_mode:=pointcloud のとき使う 3D PointCloud2 入力。",
            ),
            DeclareLaunchArgument(
                "pointcloud_z_min",
                default_value="-1.5",
                description="3D 点群入力時に中心線生成へ使う最小 z [m]。",
            ),
            DeclareLaunchArgument(
                "pointcloud_z_max",
                default_value="1.5",
                description="3D 点群入力時に中心線生成へ使う最大 z [m]。",
            ),
            DeclareLaunchArgument(
                "pointcloud_stride",
                default_value="1",
                description="3D 点群入力時に処理する点の間引き間隔。1 なら全点処理。",
            ),
            DeclareLaunchArgument(
                "odom_topic",
                default_value="/Odometry",
                description="Ego 推定に使う odometry トピック。既定では FAST-LIO の /Odometry。",
            ),
            DeclareLaunchArgument(
                "ego_output_frame",
                default_value="",
                description="Ego 出力 frame_id。空文字なら入力 odometry の frame を維持します。",
            ),
            DeclareLaunchArgument(
                "virtual_output_frame",
                default_value="",
                description="仮想経路出力 frame_id。空文字なら入力 scan の frame を維持します。",
            ),
            DeclareLaunchArgument(
                "pointcloud_to_laserscan_param_file",
                default_value=PathJoinSubstitution(
                    [adas_bringup_share, "config", "pointcloud_to_laserscan.yaml"]
                ),
                description="pointcloud_to_laserscan のパラメータファイル。",
            ),
            DeclareLaunchArgument(
                "lane_detection_model_path",
                default_value=PathJoinSubstitution(
                    [livox_lane_detection_share, "model", "livox_lane_det.ts"]
                ),
                description="livox_lane_detection が使用する TorchScript モデルパス。",
            ),
            DeclareLaunchArgument(
                "lane_detection_colored_cloud_topic",
                default_value="/livox/lane_detection/points_with_class",
                description="livox_lane_detection の色付き点群出力。",
            ),
            DeclareLaunchArgument(
                "lane_detection_scan_topic",
                default_value="/livox/lane_detection/scan",
                description="shadow_virtual_control が購読する lane-oriented LaserScan。",
            ),
            DeclareLaunchArgument(
                "lane_detection_objects_topic",
                default_value="/livox/lane_detection/objects",
                description="livox_lane_detection の障害物 JSON 出力。",
            ),
            DeclareLaunchArgument(
                "lane_detection_output_frame",
                default_value="",
                description="livox_lane_detection の出力 frame_id 上書き。空文字なら入力を維持します。",
            ),
            DeclareLaunchArgument(
                "record_shadow_bag",
                default_value="false",
                description="true のとき shadow-mode 評価用トピックを rosbag2 に記録します。",
            ),
            DeclareLaunchArgument(
                "metrics_csv_logging",
                default_value="false",
                description="true のとき shadow_mode_metrics が CSV ログも保存します。",
            ),
            DeclareLaunchArgument(
                "metrics_csv_path",
                default_value="Data/metrics/shadow_mode_metrics.csv",
                description="shadow_mode_metrics の CSV 保存先。",
            ),
            DeclareLaunchArgument(
                "bag_output",
                default_value=PathJoinSubstitution(
                    ["Data", "rosbag", "shadow_mode_bag"]
                ),
                description="rosbag2 の保存先。既存ディレクトリがあれば連番を付けます。",
            ),
            DeclareLaunchArgument(
                "bag_record_regex",
                default_value="(/shadow/.*|/livox/lane_detection/.*|/Odometry|/path|/scan)",
                description="record_shadow_bag=true のとき記録する topic regex。",
            ),
            adas_pipeline,
            ego_estimation,
            virtual_control,
            metrics,
            shadow_bag_record,
        ]
    )
