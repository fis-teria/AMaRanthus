#include "shadow_mode_virtual_control/scan_path_builder.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <string>
#include <utility>
#include <vector>

#include "tf2/LinearMath/Quaternion.h"
#include "tf2_geometry_msgs/tf2_geometry_msgs.hpp"

namespace shadow_mode_virtual_control
{

namespace
{

geometry_msgs::msg::Quaternion yawToQuaternion(double yaw)
{
  tf2::Quaternion q;
  q.setRPY(0.0, 0.0, yaw);
  return tf2::toMsg(q);
}

}  // namespace

ScanPathBuilder::ScanPathBuilder(
  double forward_min_distance,
  double forward_max_distance,
  double bin_size,
  double max_lateral_distance,
  double assumed_lane_half_width,
  std::size_t min_points_per_side)
: forward_min_distance_(forward_min_distance),
  forward_max_distance_(forward_max_distance),
  bin_size_(bin_size),
  max_lateral_distance_(max_lateral_distance),
  assumed_lane_half_width_(assumed_lane_half_width),
  min_points_per_side_(min_points_per_side)
{
}

CenterlineResult ScanPathBuilder::build(
  const sensor_msgs::msg::LaserScan & scan_msg,
  const std::string & output_frame) const
{
  CenterlineResult result;
  result.path.header.stamp = scan_msg.header.stamp;
  result.path.header.frame_id = output_frame.empty() ? scan_msg.header.frame_id : output_frame;

  if (forward_max_distance_ <= forward_min_distance_ || bin_size_ <= 0.0) {
    return result;
  }

  const std::size_t num_bins = static_cast<std::size_t>(
    std::ceil((forward_max_distance_ - forward_min_distance_) / bin_size_));

  std::vector<std::vector<double>> left_bins(num_bins);
  std::vector<std::vector<double>> right_bins(num_bins);

  for (std::size_t i = 0; i < scan_msg.ranges.size(); ++i) {
    const float range = scan_msg.ranges[i];
    if (!std::isfinite(range) || range < scan_msg.range_min || range > scan_msg.range_max) {
      continue;
    }

    const double angle = scan_msg.angle_min + static_cast<double>(i) * scan_msg.angle_increment;
    const double x = static_cast<double>(range) * std::cos(angle);
    const double y = static_cast<double>(range) * std::sin(angle);

    if (x < forward_min_distance_ || x > forward_max_distance_) {
      continue;
    }
    if (std::fabs(y) > max_lateral_distance_) {
      continue;
    }

    const std::size_t bin_index = static_cast<std::size_t>((x - forward_min_distance_) / bin_size_);
    if (bin_index >= num_bins) {
      continue;
    }

    if (y >= 0.0) {
      left_bins[bin_index].push_back(y);
    } else {
      right_bins[bin_index].push_back(y);
    }
  }

  std::size_t bins_with_missing_boundary = 0;
  std::size_t bins_with_any_boundary = 0;

  for (std::size_t bin_index = 0; bin_index < num_bins; ++bin_index) {
    const bool has_left = left_bins[bin_index].size() >= min_points_per_side_;
    const bool has_right = right_bins[bin_index].size() >= min_points_per_side_;

    if (!has_left && !has_right) {
      continue;
    }

    bins_with_any_boundary++;
    if (!(has_left && has_right)) {
      bins_with_missing_boundary++;
    }

    const double x = forward_min_distance_ + (static_cast<double>(bin_index) + 0.5) * bin_size_;

    double center_y = 0.0;
    if (has_left && has_right) {
      center_y = 0.5 * (median(left_bins[bin_index]) + median(right_bins[bin_index]));
    } else if (has_left) {
      center_y = median(left_bins[bin_index]) - assumed_lane_half_width_;
    } else {
      center_y = median(right_bins[bin_index]) + assumed_lane_half_width_;
    }

    geometry_msgs::msg::PoseStamped pose;
    pose.header = result.path.header;
    pose.pose.position.x = x;
    pose.pose.position.y = center_y;
    pose.pose.position.z = 0.0;
    pose.pose.orientation.w = 1.0;
    result.path.poses.push_back(pose);
  }

  if (result.path.poses.size() < 2) {
    result.missing_boundary_ratio = 1.0;
    return result;
  }

  for (std::size_t i = 0; i < result.path.poses.size(); ++i) {
    double yaw = 0.0;
    if (i + 1 < result.path.poses.size()) {
      const auto & current = result.path.poses[i].pose.position;
      const auto & next = result.path.poses[i + 1].pose.position;
      yaw = std::atan2(next.y - current.y, next.x - current.x);
    } else {
      const auto & prev = result.path.poses[i - 1].pose.position;
      const auto & current = result.path.poses[i].pose.position;
      yaw = std::atan2(current.y - prev.y, current.x - prev.x);
    }
    result.path.poses[i].pose.orientation = yawToQuaternion(yaw);
  }

  result.missing_boundary_ratio =
    bins_with_any_boundary == 0 ? 1.0 :
    static_cast<double>(bins_with_missing_boundary) / static_cast<double>(bins_with_any_boundary);
  result.path_curvature_proxy = computeCurvatureProxy(result.path.poses);
  result.has_path = true;
  return result;
}

double ScanPathBuilder::median(std::vector<double> values)
{
  if (values.empty()) {
    return 0.0;
  }

  std::sort(values.begin(), values.end());
  const std::size_t mid = values.size() / 2;
  if ((values.size() % 2) == 0) {
    return 0.5 * (values[mid - 1] + values[mid]);
  }
  return values[mid];
}

double ScanPathBuilder::normalizeAngle(double angle_rad)
{
  while (angle_rad > M_PI) {
    angle_rad -= 2.0 * M_PI;
  }
  while (angle_rad < -M_PI) {
    angle_rad += 2.0 * M_PI;
  }
  return angle_rad;
}

double ScanPathBuilder::computeCurvatureProxy(
  const std::vector<geometry_msgs::msg::PoseStamped> & poses)
{
  if (poses.size() < 3) {
    return 0.0;
  }

  double total_abs_curvature = 0.0;
  std::size_t count = 0;
  for (std::size_t i = 1; i + 1 < poses.size(); ++i) {
    const auto & prev = poses[i - 1].pose.position;
    const auto & current = poses[i].pose.position;
    const auto & next = poses[i + 1].pose.position;

    const double yaw_1 = std::atan2(current.y - prev.y, current.x - prev.x);
    const double yaw_2 = std::atan2(next.y - current.y, next.x - current.x);
    const double ds = std::hypot(next.x - current.x, next.y - current.y);
    if (ds <= std::numeric_limits<double>::epsilon()) {
      continue;
    }

    total_abs_curvature += std::fabs(normalizeAngle(yaw_2 - yaw_1) / ds);
    count++;
  }

  return count == 0 ? 0.0 : total_abs_curvature / static_cast<double>(count);
}

}  // namespace shadow_mode_virtual_control
