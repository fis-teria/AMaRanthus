#include "shadow_mode_virtual_control/pure_pursuit_controller.hpp"

#include <algorithm>
#include <cmath>

namespace shadow_mode_virtual_control
{

PurePursuitController::PurePursuitController(
  double wheelbase,
  double lookahead_distance,
  double max_steering_rad)
: wheelbase_(wheelbase),
  lookahead_distance_(lookahead_distance),
  max_steering_rad_(max_steering_rad)
{
  // 車両ホイールベースと先読み距離、最大舵角を設定する。
}

PurePursuitResult PurePursuitController::compute(const nav_msgs::msg::Path & path) const
{
  // 中心線経路から目標点を選択し、ステアリング角と曲率を計算する。
  PurePursuitResult result;
  if (path.poses.empty()) {
    return result;
  }

  const geometry_msgs::msg::Point * target = nullptr;
  for (const auto & pose_stamped : path.poses) {
    const auto & position = pose_stamped.pose.position;
    const double distance = std::hypot(position.x, position.y);
    if (distance >= lookahead_distance_) {
      // 先読み距離に到達した最初の点を追従ターゲットとする。
      target = &position;
      break;
    }
  }

  if (target == nullptr) {
    // 先読み点が見つからなければ経路末端を代替ターゲットにする。
    target = &path.poses.back().pose.position;
  }

  const double ld = std::max(std::hypot(target->x, target->y), 1e-3);
  // 純追従制御の曲率計算: 目標点の横方向オフセットから曲率逆数を求める。
  result.curvature_inv_m = 2.0 * target->y / (ld * ld);
  result.steering_rad = std::atan(wheelbase_ * result.curvature_inv_m);
  // 最大舵角の範囲内に制限する。
  result.steering_rad = std::clamp(result.steering_rad, -max_steering_rad_, max_steering_rad_);
  result.has_target = true;
  return result;
}

}  // namespace shadow_mode_virtual_control
