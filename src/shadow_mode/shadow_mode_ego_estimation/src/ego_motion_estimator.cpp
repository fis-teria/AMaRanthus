#include "shadow_mode_ego_estimation/ego_motion_estimator.hpp"

#include <cmath>
#include <utility>

#include "tf2_geometry_msgs/tf2_geometry_msgs.hpp"

namespace shadow_mode_ego_estimation
{

EgoMotionEstimator::EgoMotionEstimator(
  std::size_t path_buffer_size,
  double min_dt,
  double min_speed_for_curvature,
  double speed_smoothing_gain,
  double yaw_rate_smoothing_gain)
: path_buffer_size_(path_buffer_size),
  min_dt_(min_dt),
  min_speed_for_curvature_(min_speed_for_curvature),
  speed_smoothing_gain_(speed_smoothing_gain),
  yaw_rate_smoothing_gain_(yaw_rate_smoothing_gain)
{
}

EgoMotionState EgoMotionEstimator::update(const nav_msgs::msg::Odometry & odom_msg)
{
  // odometry からサンプルを作成し、バッファに追加して状態を更新する。
  auto sample = makeSample(odom_msg);
  if (!sample.has_value()) {
    return last_state_;
  }

  if (!samples_.empty()) {
    const auto & prev = samples_.back();
    const double dt = (sample->stamp - prev.stamp).seconds();
    // サンプル間隔が小さすぎる場合は計算をスキップしてノイズを避ける。
    if (dt < min_dt_) {
      return last_state_;
    }

    const double dx = sample->x - prev.x;
    const double dy = sample->y - prev.y;
    const double distance = std::hypot(dx, dy);
    const double raw_speed = distance / dt;
    const double raw_yaw_rate = normalizeAngle(sample->yaw - prev.yaw) / dt;

    if (!last_state_.has_estimate) {
      // 初回は生の速度・ヨーレートをそのまま初期値として採用。
      last_state_.speed_mps = raw_speed;
      last_state_.yaw_rate_rps = raw_yaw_rate;
      last_state_.has_estimate = true;
    } else {
      // 前回推定値と新規生値を平滑化して安定化させる。
      last_state_.speed_mps += speed_smoothing_gain_ * (raw_speed - last_state_.speed_mps);
      last_state_.yaw_rate_rps +=
        yaw_rate_smoothing_gain_ * (raw_yaw_rate - last_state_.yaw_rate_rps);
    }

    if (std::fabs(last_state_.speed_mps) >= min_speed_for_curvature_) {
      // 速度が十分に大きい場合のみ曲率を計算し、低速時は 0 にする。
      last_state_.curvature_inv_m = last_state_.yaw_rate_rps / last_state_.speed_mps;
    } else {
      last_state_.curvature_inv_m = 0.0;
    }
  }

  samples_.push_back(std::move(*sample));
  // バッファサイズを超えた古いサンプルは順次削除する。
  while (samples_.size() > path_buffer_size_) {
    samples_.pop_front();
  }

  return last_state_;
}

nav_msgs::msg::Path EgoMotionEstimator::buildPath(const std::string & frame_id) const
{
  nav_msgs::msg::Path path;
  path.header.frame_id = frame_id;

  if (!samples_.empty()) {
    path.header.stamp = samples_.back().stamp;
  }

  for (const auto & sample : samples_) {
    path.poses.push_back(sample.pose);
  }

  return path;
}

std::optional<EgoMotionEstimator::Sample> EgoMotionEstimator::makeSample(
  const nav_msgs::msg::Odometry & odom_msg) const
{
  // Odometry から座標と姿勢を抽出し、内部バッファ用のサンプル構造体を生成する。
  Sample sample;
  sample.stamp = odom_msg.header.stamp;
  sample.x = odom_msg.pose.pose.position.x;
  sample.y = odom_msg.pose.pose.position.y;
  sample.yaw = yawFromQuaternion(odom_msg.pose.pose.orientation);
  sample.pose.header = odom_msg.header;
  sample.pose.pose = odom_msg.pose.pose;
  return sample;
}

double EgoMotionEstimator::normalizeAngle(double angle_rad)
{
  // 角度を [-pi, pi] の範囲に正規化する。
  while (angle_rad > M_PI) {
    angle_rad -= 2.0 * M_PI;
  }
  while (angle_rad < -M_PI) {
    angle_rad += 2.0 * M_PI;
  }
  return angle_rad;
}

double EgoMotionEstimator::yawFromQuaternion(const geometry_msgs::msg::Quaternion & q)
{
  // クォータニオンから航向 (yaw) を抽出する。
  tf2::Quaternion tf_q(q.x, q.y, q.z, q.w);
  double roll = 0.0;
  double pitch = 0.0;
  double yaw = 0.0;
  tf2::Matrix3x3(tf_q).getRPY(roll, pitch, yaw);
  return yaw;
}

}  // namespace shadow_mode_ego_estimation
