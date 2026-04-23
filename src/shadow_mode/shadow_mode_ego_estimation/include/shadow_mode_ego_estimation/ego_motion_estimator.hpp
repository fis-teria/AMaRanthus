#ifndef SHADOW_MODE_EGO_ESTIMATION__EGO_MOTION_ESTIMATOR_HPP_
#define SHADOW_MODE_EGO_ESTIMATION__EGO_MOTION_ESTIMATOR_HPP_

#include <cstddef>
#include <deque>
#include <optional>

#include "geometry_msgs/msg/pose_stamped.hpp"
#include "nav_msgs/msg/odometry.hpp"
#include "nav_msgs/msg/path.hpp"
#include "rclcpp/rclcpp.hpp"

namespace shadow_mode_ego_estimation
{

/// odometry から推定した ego state を保持する構造体。
struct EgoMotionState
{
  double speed_mps {0.0};            ///< 推定速度 [m/s]
  double yaw_rate_rps {0.0};         ///< 推定ヨーレート [rad/s]
  double curvature_inv_m {0.0};      ///< 推定曲率の逆数 [1/m]
  bool has_estimate {false};          ///< 推定値が利用可能かどうか
};

/// 過去の odometry をバッファリングし、
/// シャドウモード用の経路と運動状態を推定するクラス。
class EgoMotionEstimator
{
public:
  EgoMotionEstimator(
    std::size_t path_buffer_size,
    double min_dt,
    double min_speed_for_curvature,
    double speed_smoothing_gain,
    double yaw_rate_smoothing_gain);

  /// 新しい odometry を受け取り、最新の運動状態を計算する。
  EgoMotionState update(const nav_msgs::msg::Odometry & odom_msg);

  /// 保存済みのサンプルから nav_msgs::msg::Path を構築する。
  nav_msgs::msg::Path buildPath(const std::string & frame_id) const;

private:
  struct Sample
  {
    rclcpp::Time stamp;
    double x {0.0};
    double y {0.0};
    double yaw {0.0};
    geometry_msgs::msg::PoseStamped pose;
  };

  std::optional<Sample> makeSample(const nav_msgs::msg::Odometry & odom_msg) const;
  static double normalizeAngle(double angle_rad);
  static double yawFromQuaternion(const geometry_msgs::msg::Quaternion & q);

  std::size_t path_buffer_size_;
  double min_dt_;
  double min_speed_for_curvature_;
  double speed_smoothing_gain_;
  double yaw_rate_smoothing_gain_;

  std::deque<Sample> samples_;
  EgoMotionState last_state_;
};

}  // namespace shadow_mode_ego_estimation

#endif  // SHADOW_MODE_EGO_ESTIMATION__EGO_MOTION_ESTIMATOR_HPP_
