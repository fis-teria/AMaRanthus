import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    IncludeLaunchDescription,
    OpaqueFunction,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def _as_bool(value):
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _optional_adas_pipeline(context):
    if not _as_bool(LaunchConfiguration("use_adas_bringup").perform(context)):
        return []

    adas_bringup_share = get_package_share_directory("adas_bringup")

    pointcloud_to_laserscan_param_file = LaunchConfiguration(
        "pointcloud_to_laserscan_param_file"
    ).perform(context)
    if not pointcloud_to_laserscan_param_file:
        pointcloud_to_laserscan_param_file = os.path.join(
            adas_bringup_share,
            "config",
            "pointcloud_to_laserscan.yaml",
        )

    lane_detection_model_path = LaunchConfiguration("lane_detection_model_path").perform(context)
    if not lane_detection_model_path:
        lane_detection_share = get_package_share_directory("livox_lane_detection")
        lane_detection_model_path = os.path.join(
            lane_detection_share,
            "model",
            "livox_lane_det.ts",
        )

    return [
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(
                    adas_bringup_share,
                    "launch",
                    "adas_bringup.launch.py",
                )
            ),
            launch_arguments={
                "use_livox_rviz": LaunchConfiguration("use_livox_rviz"),
                "pointcloud_topic": LaunchConfiguration("pointcloud_topic"),
                "scan_topic": LaunchConfiguration("scan_topic"),
                "pointcloud_to_laserscan_param_file": pointcloud_to_laserscan_param_file,
                "lane_detection_model_path": lane_detection_model_path,
                "lane_detection_colored_cloud_topic": LaunchConfiguration(
                    "lane_detection_colored_cloud_topic"
                ),
                "lane_detection_scan_topic": LaunchConfiguration("lane_detection_scan_topic"),
                "lane_detection_objects_topic": LaunchConfiguration("lane_detection_objects_topic"),
                "lane_detection_output_frame": LaunchConfiguration(
                    "lane_detection_output_frame"
                ),
            }.items(),
        )
    ]


def _optional_fast_lio(context):
    if not _as_bool(LaunchConfiguration("use_fast_lio").perform(context)):
        return []

    fast_lio_share = get_package_share_directory("fast_lio")

    fast_lio_config_path = LaunchConfiguration("fast_lio_config_path").perform(context)
    if not fast_lio_config_path:
        fast_lio_config_path = os.path.join(fast_lio_share, "config")

    fast_lio_rviz_cfg = LaunchConfiguration("fast_lio_rviz_cfg").perform(context)
    if not fast_lio_rviz_cfg:
        fast_lio_rviz_cfg = os.path.join(fast_lio_share, "rviz", "fastlio.rviz")

    return [
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(
                    fast_lio_share,
                    "launch",
                    "mapping.launch.py",
                )
            ),
            launch_arguments={
                "use_sim_time": LaunchConfiguration("use_sim_time"),
                "config_path": fast_lio_config_path,
                "config_file": LaunchConfiguration("fast_lio_config_file"),
                "rviz": LaunchConfiguration("use_fast_lio_rviz"),
                "rviz_cfg": fast_lio_rviz_cfg,
            }.items(),
        )
    ]


def generate_launch_description():
    use_ego_estimation = LaunchConfiguration("use_ego_estimation")
    use_virtual_control = LaunchConfiguration("use_virtual_control")
    use_route_target = LaunchConfiguration("use_route_target")
    use_metrics = LaunchConfiguration("use_metrics")
    use_phone_location_bridge = LaunchConfiguration("use_phone_location_bridge")
    use_localization_fusion = LaunchConfiguration("use_localization_fusion")
    record_shadow_bag = LaunchConfiguration("record_shadow_bag")

    virtual_input_mode = LaunchConfiguration("virtual_input_mode")
    virtual_pointcloud_topic = LaunchConfiguration("virtual_pointcloud_topic")
    pointcloud_z_min = LaunchConfiguration("pointcloud_z_min")
    pointcloud_z_max = LaunchConfiguration("pointcloud_z_max")
    pointcloud_stride = LaunchConfiguration("pointcloud_stride")
    odom_topic = LaunchConfiguration("odom_topic")
    localization_fusion_param_file = LaunchConfiguration("localization_fusion_param_file")
    localization_lidar_odom_topic = LaunchConfiguration("localization_lidar_odom_topic")
    phone_fix_topic = LaunchConfiguration("phone_fix_topic")
    spresense_fix_topic = LaunchConfiguration("spresense_fix_topic")
    fused_odom_topic = LaunchConfiguration("fused_odom_topic")
    fused_path_topic = LaunchConfiguration("fused_path_topic")
    fused_status_topic = LaunchConfiguration("fused_status_topic")
    ego_output_frame = LaunchConfiguration("ego_output_frame")
    virtual_output_frame = LaunchConfiguration("virtual_output_frame")

    shadow_mode_param_file = LaunchConfiguration("shadow_mode_param_file")
    route_target_param_file = LaunchConfiguration("route_target_param_file")
    lane_detection_scan_topic = LaunchConfiguration("lane_detection_scan_topic")

    bag_output = LaunchConfiguration("bag_output")
    bag_record_regex = LaunchConfiguration("bag_record_regex")
    metrics_csv_logging = LaunchConfiguration("metrics_csv_logging")
    metrics_csv_path = LaunchConfiguration("metrics_csv_path")

    shadow_bringup_share = FindPackageShare("shadow_mode_bringup")
    localization_fusion_share = FindPackageShare("shadow_mode_localization_fusion")
    route_target_share = FindPackageShare("shadow_route_target")

    phone_location_bridge = Node(
        package="phone_location_bridge",
        executable="phone_location_bridge_node.py",
        name="phone_location_bridge",
        output="screen",
        parameters=[
            {
                "server_host": LaunchConfiguration("phone_bridge_server_host"),
                "server_port": ParameterValue(
                    LaunchConfiguration("phone_bridge_server_port"), value_type=int
                ),
                "use_https": ParameterValue(
                    LaunchConfiguration("phone_bridge_use_https"), value_type=bool
                ),
                "tls_cert_file": LaunchConfiguration("phone_bridge_tls_cert_file"),
                "tls_key_file": LaunchConfiguration("phone_bridge_tls_key_file"),
                "osrm_service_url": LaunchConfiguration("phone_bridge_osrm_service_url"),
                "publish_rate_hz": ParameterValue(
                    LaunchConfiguration("phone_bridge_publish_rate_hz"),
                    value_type=float,
                ),
                "fix_stale_timeout_sec": ParameterValue(
                    LaunchConfiguration("phone_bridge_fix_stale_timeout_sec"),
                    value_type=float,
                ),
                "fix_topic": LaunchConfiguration("phone_bridge_fix_topic"),
                "goal_topic": LaunchConfiguration("phone_bridge_goal_topic"),
                "route_path_topic": LaunchConfiguration("gui_route_path_topic"),
                "gps_status_topic": LaunchConfiguration("phone_bridge_gps_status_topic"),
                "status_topic": LaunchConfiguration("phone_bridge_status_topic"),
                "route_frame_id": LaunchConfiguration("route_target_default_frame_id"),
                "path_step_m": ParameterValue(
                    LaunchConfiguration("phone_bridge_path_step_m"),
                    value_type=float,
                ),
                "max_path_length_m": ParameterValue(
                    LaunchConfiguration("phone_bridge_max_path_length_m"),
                    value_type=float,
                ),
                "route_command_topic": LaunchConfiguration("route_command_topic"),
                "route_command": LaunchConfiguration("phone_bridge_route_command"),
                "auto_reroute_enabled": ParameterValue(
                    LaunchConfiguration("phone_bridge_auto_reroute_enabled"),
                    value_type=bool,
                ),
                "off_route_threshold_m": ParameterValue(
                    LaunchConfiguration("phone_bridge_off_route_threshold_m"),
                    value_type=float,
                ),
                "off_route_hold_sec": ParameterValue(
                    LaunchConfiguration("phone_bridge_off_route_hold_sec"),
                    value_type=float,
                ),
                "reroute_cooldown_sec": ParameterValue(
                    LaunchConfiguration("phone_bridge_reroute_cooldown_sec"),
                    value_type=float,
                ),
            }
        ],
        condition=IfCondition(use_phone_location_bridge),
    )

    localization_fusion = Node(
        package="shadow_mode_localization_fusion",
        executable="shadow_localization_fusion_node.py",
        name="shadow_localization_fusion",
        output="screen",
        parameters=[
            localization_fusion_param_file,
            {
                "lidar_odom_topic": localization_lidar_odom_topic,
                "phone_fix_topic": phone_fix_topic,
                "spresense_fix_topic": spresense_fix_topic,
                "fused_odom_topic": fused_odom_topic,
                "fused_path_topic": fused_path_topic,
                "status_topic": fused_status_topic,
                "fix_timeout_sec": ParameterValue(
                    LaunchConfiguration("localization_fix_timeout_sec"), value_type=float
                ),
                "max_fix_accuracy_m": ParameterValue(
                    LaunchConfiguration("localization_max_fix_accuracy_m"), value_type=float
                ),
                "correction_gain": ParameterValue(
                    LaunchConfiguration("localization_correction_gain"), value_type=float
                ),
                "dynamic_correction_gain": ParameterValue(
                    LaunchConfiguration("localization_dynamic_correction_gain"),
                    value_type=bool,
                ),
                "low_speed_threshold_mps": ParameterValue(
                    LaunchConfiguration("localization_low_speed_threshold_mps"),
                    value_type=float,
                ),
                "high_speed_threshold_mps": ParameterValue(
                    LaunchConfiguration("localization_high_speed_threshold_mps"),
                    value_type=float,
                ),
                "high_speed_correction_gain": ParameterValue(
                    LaunchConfiguration("localization_high_speed_correction_gain"),
                    value_type=float,
                ),
                "high_speed_max_correction_step_m": ParameterValue(
                    LaunchConfiguration("localization_high_speed_max_correction_step_m"),
                    value_type=float,
                ),
            },
        ],
        condition=IfCondition(use_localization_fusion),
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

    route_target = Node(
        package="shadow_route_target",
        executable="shadow_route_target_node.py",
        name="shadow_route_target",
        output="screen",
        parameters=[
            route_target_param_file,
            {
                "output_topic": LaunchConfiguration("route_target_output_topic"),
                "output_path_topic": LaunchConfiguration("route_target_output_path_topic"),
                "status_topic": LaunchConfiguration("route_target_status_topic"),
                "route_command_topic": LaunchConfiguration("route_command_topic"),
                "publish_rate_hz": ParameterValue(
                    LaunchConfiguration("route_target_publish_rate_hz"), value_type=float
                ),
                "input_timeout_sec": ParameterValue(
                    LaunchConfiguration("route_target_input_timeout_sec"), value_type=float
                ),
                "lookahead_distance_m": ParameterValue(
                    LaunchConfiguration("route_target_lookahead_distance_m"), value_type=float
                ),
                "speed_adaptive_lookahead": ParameterValue(
                    LaunchConfiguration("route_target_speed_adaptive_lookahead"),
                    value_type=bool,
                ),
                "lookahead_time_sec": ParameterValue(
                    LaunchConfiguration("route_target_lookahead_time_sec"), value_type=float
                ),
                "max_lookahead_distance_m": ParameterValue(
                    LaunchConfiguration("route_target_max_lookahead_distance_m"),
                    value_type=float,
                ),
                "min_forward_distance_m": ParameterValue(
                    LaunchConfiguration("route_target_min_forward_distance_m"), value_type=float
                ),
                "odom_topic": LaunchConfiguration("odom_topic"),
                "source_priority": LaunchConfiguration("route_target_source_priority"),
                "gui_route_path_topic": LaunchConfiguration("gui_route_path_topic"),
                "image_lane_path_topic": LaunchConfiguration("image_lane_path_topic"),
                "shadow_virtual_path_topic": LaunchConfiguration("shadow_virtual_path_topic"),
                "default_frame_id": LaunchConfiguration("route_target_default_frame_id"),
                "default_target_x_m": ParameterValue(
                    LaunchConfiguration("route_target_default_x_m"), value_type=float
                ),
                "default_target_y_m": ParameterValue(
                    LaunchConfiguration("route_target_default_y_m"), value_type=float
                ),
                "publish_default_when_missing": ParameterValue(
                    LaunchConfiguration("route_target_publish_default_when_missing"),
                    value_type=bool,
                ),
            },
        ],
        condition=IfCondition(use_route_target),
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
                "use_fast_lio",
                default_value=LaunchConfiguration("use_adas_bringup"),
                description=(
                    "FAST-LIO2 (fast_lio mapping.launch.py) を起動します。"
                    "既定では use_adas_bringup と同じ値です。"
                ),
            ),
            DeclareLaunchArgument(
                "use_sim_time",
                default_value="false",
                description="FAST-LIO2 に渡す use_sim_time。",
            ),
            DeclareLaunchArgument(
                "fast_lio_config_path",
                default_value="",
                description="FAST-LIO2 config ディレクトリ。空なら fast_lio の既定 config を使います。",
            ),
            DeclareLaunchArgument(
                "fast_lio_config_file",
                default_value="mid360.yaml",
                description="FAST-LIO2 の config ファイル名。",
            ),
            DeclareLaunchArgument(
                "use_fast_lio_rviz",
                default_value="false",
                description="FAST-LIO2 付属 RViz を起動します。",
            ),
            DeclareLaunchArgument(
                "fast_lio_rviz_cfg",
                default_value="",
                description="FAST-LIO2 RViz config。空なら fast_lio の既定 RViz config を使います。",
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
                "use_route_target",
                default_value="true",
                description=(
                    "shadow_route_target を起動し、Shadow/GUI route path から "
                    "/shadow/route/target_point を生成します。"
                ),
            ),
            DeclareLaunchArgument(
                "use_metrics",
                default_value="true",
                description="shadow_mode_metrics を起動して ego と virtual control を比較します。",
            ),
            DeclareLaunchArgument(
                "use_phone_location_bridge",
                default_value="false",
                description="USB tethered phone location web bridge を起動します。",
            ),
            DeclareLaunchArgument(
                "use_localization_fusion",
                default_value="false",
                description="LiDAR odometry と phone/Spresense NavSatFix の融合 odometry を起動します。",
            ),
            DeclareLaunchArgument(
                "shadow_mode_param_file",
                default_value=PathJoinSubstitution(
                    [shadow_bringup_share, "config", "shadow_mode_bringup.param.yaml"]
                ),
                description="Shadow-mode ノード群の共通パラメータファイル。",
            ),
            DeclareLaunchArgument(
                "route_target_param_file",
                default_value=PathJoinSubstitution(
                    [route_target_share, "config", "shadow_route_target.param.yaml"]
                ),
                description="shadow_route_target のパラメータファイル。",
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
                "localization_fusion_param_file",
                default_value=PathJoinSubstitution(
                    [
                        localization_fusion_share,
                        "config",
                        "shadow_localization_fusion.param.yaml",
                    ]
                ),
                description="shadow_mode_localization_fusion のパラメータファイル。",
            ),
            DeclareLaunchArgument(
                "localization_lidar_odom_topic",
                default_value="/Odometry",
                description="融合ノードが購読する LiDAR odometry 入力。",
            ),
            DeclareLaunchArgument(
                "phone_fix_topic",
                default_value="/phone/gps/fix",
                description="融合ノードが購読するスマホ NavSatFix。",
            ),
            DeclareLaunchArgument(
                "spresense_fix_topic",
                default_value="/spresense/gps/fix",
                description="融合ノードが購読する Spresense NavSatFix。",
            ),
            DeclareLaunchArgument(
                "fused_odom_topic",
                default_value="/shadow/fused/odometry",
                description="融合ノードが publish する odometry。",
            ),
            DeclareLaunchArgument(
                "fused_path_topic",
                default_value="/shadow/fused/path",
                description="融合ノードが publish する path。",
            ),
            DeclareLaunchArgument(
                "fused_status_topic",
                default_value="/shadow/fused/status",
                description="融合ノードの JSON status topic。",
            ),
            DeclareLaunchArgument(
                "localization_fix_timeout_sec",
                default_value="3.0",
                description="GNSS fix を fresh とみなす秒数。",
            ),
            DeclareLaunchArgument(
                "localization_max_fix_accuracy_m",
                default_value="25.0",
                description="融合に使う最大 GNSS accuracy [m]。",
            ),
            DeclareLaunchArgument(
                "localization_correction_gain",
                default_value="0.08",
                description="低速時に GNSS 残差を LiDAR odometry に反映する低周波ゲイン。",
            ),
            DeclareLaunchArgument(
                "localization_dynamic_correction_gain",
                default_value="true",
                description="速度に応じて GNSS 補正ゲインと補正ステップを下げます。",
            ),
            DeclareLaunchArgument(
                "localization_low_speed_threshold_mps",
                default_value="3.0",
                description="この速度以下では低速用 GNSS 補正ゲインを使います。",
            ),
            DeclareLaunchArgument(
                "localization_high_speed_threshold_mps",
                default_value="20.0",
                description="この速度以上では高速用 GNSS 補正ゲインを使います。",
            ),
            DeclareLaunchArgument(
                "localization_high_speed_correction_gain",
                default_value="0.01",
                description="高速時に使う GNSS 残差補正ゲイン。",
            ),
            DeclareLaunchArgument(
                "localization_high_speed_max_correction_step_m",
                default_value="0.05",
                description="高速時の 1 odom callback あたり最大 GNSS 補正量 [m]。",
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
                "route_target_output_topic",
                default_value="/shadow/route/target_point",
                description="E2E TransFuser に渡す route target topic。",
            ),
            DeclareLaunchArgument(
                "route_target_output_path_topic",
                default_value="/shadow/route/target_path",
                description="E2E TransFuser の previous/current/next target 用 Path topic。",
            ),
            DeclareLaunchArgument(
                "route_target_status_topic",
                default_value="/shadow/route/target_status",
                description="route target 選択状態の JSON status topic。",
            ),
            DeclareLaunchArgument(
                "route_command_topic",
                default_value="/shadow/route/command",
                description="E2E TransFuser に渡す route command topic。",
            ),
            DeclareLaunchArgument(
                "route_target_publish_rate_hz",
                default_value="10.0",
                description="route target publish rate。",
            ),
            DeclareLaunchArgument(
                "route_target_input_timeout_sec",
                default_value="0.5",
                description="route path 入力の freshness timeout。",
            ),
            DeclareLaunchArgument(
                "route_target_lookahead_distance_m",
                default_value="15.0",
                description="route path から選ぶ target lookahead 距離 [m]。",
            ),
            DeclareLaunchArgument(
                "route_target_speed_adaptive_lookahead",
                default_value="true",
                description="速度に応じて route target lookahead を伸ばします。",
            ),
            DeclareLaunchArgument(
                "route_target_lookahead_time_sec",
                default_value="1.2",
                description="速度連動 lookahead に使う時間 horizon [s]。",
            ),
            DeclareLaunchArgument(
                "route_target_max_lookahead_distance_m",
                default_value="60.0",
                description="速度連動 route target lookahead の上限 [m]。",
            ),
            DeclareLaunchArgument(
                "route_target_min_forward_distance_m",
                default_value="1.0",
                description="target 候補として許容する最小前方距離 [m]。",
            ),
            DeclareLaunchArgument(
                "route_target_source_priority",
                default_value="gui_route,image_lane,shadow_virtual",
                description="route target source 優先順。",
            ),
            DeclareLaunchArgument(
                "gui_route_path_topic",
                default_value="/shadow/route/gui_path",
                description="GUI route IF。base_link の nav_msgs/Path を想定。",
            ),
            DeclareLaunchArgument(
                "image_lane_path_topic",
                default_value="/shadow/perception/lane_path",
                description="画像白線/路肩検知 route IF。base_link の nav_msgs/Path を想定。",
            ),
            DeclareLaunchArgument(
                "shadow_virtual_path_topic",
                default_value="/shadow/virtual/path",
                description="shadow_virtual_control の path 入力。",
            ),
            DeclareLaunchArgument(
                "route_target_default_frame_id",
                default_value="base_link",
                description="fallback target の frame_id。",
            ),
            DeclareLaunchArgument(
                "route_target_default_x_m",
                default_value="15.0",
                description="fallback target x [m]。",
            ),
            DeclareLaunchArgument(
                "route_target_default_y_m",
                default_value="0.0",
                description="fallback target y [m]。",
            ),
            DeclareLaunchArgument(
                "route_target_publish_default_when_missing",
                default_value="false",
                description="route path が無いとき固定前方 target を publish するか。",
            ),
            DeclareLaunchArgument(
                "phone_bridge_server_host",
                default_value="0.0.0.0",
                description="phone_location_bridge の HTTP bind address。",
            ),
            DeclareLaunchArgument(
                "phone_bridge_server_port",
                default_value="8765",
                description="phone_location_bridge の HTTP port。",
            ),
            DeclareLaunchArgument(
                "phone_bridge_use_https",
                default_value="false",
                description="phone_location_bridge を HTTPS で起動します。",
            ),
            DeclareLaunchArgument(
                "phone_bridge_tls_cert_file",
                default_value="",
                description="HTTPS 用 TLS certificate file。",
            ),
            DeclareLaunchArgument(
                "phone_bridge_tls_key_file",
                default_value="",
                description="HTTPS 用 TLS private key file。",
            ),
            DeclareLaunchArgument(
                "phone_bridge_osrm_service_url",
                default_value="https://routing.openstreetmap.de/routed-car/route/v1/driving",
                description="OSRM route API endpoint。",
            ),
            DeclareLaunchArgument(
                "phone_bridge_publish_rate_hz",
                default_value="10.0",
                description="phone bridge が現在地/route path を再publishする周期 [Hz]。",
            ),
            DeclareLaunchArgument(
                "phone_bridge_fix_stale_timeout_sec",
                default_value="3.0",
                description="スマホ現在地を fresh とみなして publish する最大 age [s]。",
            ),
            DeclareLaunchArgument(
                "phone_bridge_fix_topic",
                default_value="/phone/gps/fix",
                description="スマホ現在地 NavSatFix topic。",
            ),
            DeclareLaunchArgument(
                "phone_bridge_goal_topic",
                default_value="/phone/route/goal",
                description="スマホ目的地 JSON topic。",
            ),
            DeclareLaunchArgument(
                "phone_bridge_gps_status_topic",
                default_value="/vehicle/gps_status",
                description="GUI top status 用 GPS status topic。",
            ),
            DeclareLaunchArgument(
                "phone_bridge_status_topic",
                default_value="/phone/location/status",
                description="phone_location_bridge health/status JSON topic。",
            ),
            DeclareLaunchArgument(
                "phone_bridge_path_step_m",
                default_value="2.0",
                description="phone bridge が出す /shadow/route/gui_path の点間隔 [m]。",
            ),
            DeclareLaunchArgument(
                "phone_bridge_max_path_length_m",
                default_value="400.0",
                description="phone bridge が出す /shadow/route/gui_path の最大長 [m]。",
            ),
            DeclareLaunchArgument(
                "phone_bridge_route_command",
                default_value="lane_follow",
                description="スマホ route 受信時に publish する route command。",
            ),
            DeclareLaunchArgument(
                "phone_bridge_auto_reroute_enabled",
                default_value="true",
                description="OSRM ルートから外れたときに自動再検索します。",
            ),
            DeclareLaunchArgument(
                "phone_bridge_off_route_threshold_m",
                default_value="30.0",
                description="自動再検索判定に使うルート逸脱距離。",
            ),
            DeclareLaunchArgument(
                "phone_bridge_off_route_hold_sec",
                default_value="3.0",
                description="ルート逸脱が継続したとみなすまでの秒数。",
            ),
            DeclareLaunchArgument(
                "phone_bridge_reroute_cooldown_sec",
                default_value="10.0",
                description="自動再検索後の最小クールダウン秒数。",
            ),
            DeclareLaunchArgument(
                "pointcloud_to_laserscan_param_file",
                default_value="",
                description=(
                    "pointcloud_to_laserscan のパラメータファイル。"
                    "空なら use_adas_bringup=true 時に adas_bringup の既定ファイルを使います。"
                ),
            ),
            DeclareLaunchArgument(
                "lane_detection_model_path",
                default_value="",
                description=(
                    "livox_lane_detection が使用する TorchScript モデルパス。"
                    "空なら use_adas_bringup=true 時に livox_lane_detection の既定モデルを使います。"
                ),
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
                default_value=(
                    "(/shadow/.*|/livox/lane_detection/.*|/yolo/.*|/Odometry|/path|/scan|"
                    "/cloud_registered|/cloud_registered_body|/tf|/tf_static|"
                    "/sensing/camera/.*|/phone/.*|/spresense/gps/fix|/vehicle/gps_status)"
                ),
                description="record_shadow_bag=true のとき記録する topic regex。",
            ),
            OpaqueFunction(function=_optional_adas_pipeline),
            OpaqueFunction(function=_optional_fast_lio),
            phone_location_bridge,
            localization_fusion,
            ego_estimation,
            virtual_control,
            route_target,
            metrics,
            shadow_bag_record,
        ]
    )
