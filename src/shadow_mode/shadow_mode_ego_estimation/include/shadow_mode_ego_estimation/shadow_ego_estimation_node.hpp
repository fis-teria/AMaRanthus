#ifndef SHADOW_MODE_EGO_ESTIMATION__SHADOW_EGO_ESTIMATION_NODE_HPP_
#define SHADOW_MODE_EGO_ESTIMATION__SHADOW_EGO_ESTIMATION_NODE_HPP_

#include <memory>
#include <string>

#include "nav_msgs/msg/odometry.hpp"
#include "nav_msgs/msg/path.hpp"
#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/float32.hpp"
#include "visualization_msgs/msg/marker_array.hpp"

#include "shadow_mode_ego_estimation/ego_motion_estimator.hpp"

namespace shadow_mode_ego_estimation
{

/// 実車両またはシミュレーションの odometry を受け取り、
/// シャドウモード用の ego motion を計算して公開するノード。
class ShadowEgoEstimationNode : public rclcpp::Node
{
public:
  ShadowEgoEstimationNode();

private:
  /// 受信した odometry を元に状態を更新し、
  /// パス・速度・ヨーレート・曲率などを公開するコールバック。
  void odomCallback(const nav_msgs::msg::Odometry::SharedPtr msg);

  std::string output_frame_;
  bool publish_debug_markers_ {true};

  std::unique_ptr<EgoMotionEstimator> estimator_;

  rclcpp::Subscription<nav_msgs::msg::Odometry>::SharedPtr odom_sub_;
  rclcpp::Publisher<nav_msgs::msg::Path>::SharedPtr ego_path_pub_;
  rclcpp::Publisher<std_msgs::msg::Float32>::SharedPtr ego_speed_pub_;
  rclcpp::Publisher<std_msgs::msg::Float32>::SharedPtr ego_yaw_rate_pub_;
  rclcpp::Publisher<std_msgs::msg::Float32>::SharedPtr ego_curvature_pub_;
  rclcpp::Publisher<visualization_msgs::msg::MarkerArray>::SharedPtr ego_debug_markers_pub_;
};

}  // namespace shadow_mode_ego_estimation

#endif  // SHADOW_MODE_EGO_ESTIMATION__SHADOW_EGO_ESTIMATION_NODE_HPP_
