#ifndef SHADOW_MODE_VIRTUAL_CONTROL__SHADOW_VIRTUAL_CONTROL_NODE_HPP_
#define SHADOW_MODE_VIRTUAL_CONTROL__SHADOW_VIRTUAL_CONTROL_NODE_HPP_

#include <memory>
#include <string>

#include "nav_msgs/msg/path.hpp"
#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/laser_scan.hpp"
#include "sensor_msgs/msg/point_cloud2.hpp"
#include "std_msgs/msg/float32.hpp"
#include "visualization_msgs/msg/marker_array.hpp"

#include "shadow_mode_virtual_control/pure_pursuit_controller.hpp"
#include "shadow_mode_virtual_control/scan_path_builder.hpp"

namespace shadow_mode_virtual_control
{

/// LiDAR の LaserScan から仮想経路と制御値を生成するノード。
/// シャドウモードの仮想制御出力を公開する。
class ShadowVirtualControlNode : public rclcpp::Node
{
public:
  ShadowVirtualControlNode();

private:
  /// スキャンデータを受け取り、中心線と制御情報を計算して公開する。
  void scanCallback(const sensor_msgs::msg::LaserScan::SharedPtr msg);
  /// 3D 点群を受け取り、地面投影した中心線と制御情報を計算して公開する。
  void pointCloudCallback(const sensor_msgs::msg::PointCloud2::SharedPtr msg);
  /// 入力種別に依存しない仮想制御 publish 処理。
  void publishControlFromCenterline(const CenterlineResult & centerline, const rclcpp::Time & stamp);
  /// 計算した中心線経路を可視化するためのマーカー配列を作成する。
  visualization_msgs::msg::MarkerArray buildDebugMarkers(
    const nav_msgs::msg::Path & path,
    const std::string & frame_id,
    const rclcpp::Time & stamp) const;

  std::string output_frame_;
  bool publish_debug_markers_ {true};
  double warning_missing_boundary_weight_ {0.7};
  double warning_curvature_weight_ {0.3};
  double pointcloud_z_min_ {-1.5};
  double pointcloud_z_max_ {1.5};
  std::size_t pointcloud_stride_ {1};

  std::unique_ptr<ScanPathBuilder> path_builder_;
  std::unique_ptr<PurePursuitController> controller_;

  rclcpp::Subscription<sensor_msgs::msg::LaserScan>::SharedPtr scan_sub_;
  rclcpp::Subscription<sensor_msgs::msg::PointCloud2>::SharedPtr pointcloud_sub_;
  rclcpp::Publisher<nav_msgs::msg::Path>::SharedPtr virtual_path_pub_;
  rclcpp::Publisher<std_msgs::msg::Float32>::SharedPtr virtual_steering_pub_;
  rclcpp::Publisher<std_msgs::msg::Float32>::SharedPtr virtual_curvature_pub_;
  rclcpp::Publisher<std_msgs::msg::Float32>::SharedPtr warning_score_pub_;
  rclcpp::Publisher<visualization_msgs::msg::MarkerArray>::SharedPtr debug_markers_pub_;
};

}  // namespace shadow_mode_virtual_control

#endif  // SHADOW_MODE_VIRTUAL_CONTROL__SHADOW_VIRTUAL_CONTROL_NODE_HPP_
