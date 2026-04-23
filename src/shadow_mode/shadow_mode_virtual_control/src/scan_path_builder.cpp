#include "shadow_mode_virtual_control/scan_path_builder.hpp"

#include <algorithm>
#include <cmath>
#include <exception>
#include <limits>
#include <string>
#include <utility>
#include <vector>

#include "sensor_msgs/point_cloud2_iterator.hpp"
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
  // レーザースキャンを前方ビンに分割し、左右境界点から中心線を算出する。
  const std::size_t num_bins = computeBinCount();
  LateralBins left_bins(num_bins);
  LateralBins right_bins(num_bins);

  if (num_bins == 0) {
    return buildPathFromBins(scan_msg.header, output_frame, left_bins, right_bins);
  }

  for (std::size_t i = 0; i < scan_msg.ranges.size(); ++i) {
    const float range = scan_msg.ranges[i];
    if (!std::isfinite(range) || range < scan_msg.range_min || range > scan_msg.range_max) {
      // 無効な測距値はスキップする。
      continue;
    }

    const double angle = scan_msg.angle_min + static_cast<double>(i) * scan_msg.angle_increment;
    const double x = static_cast<double>(range) * std::cos(angle);
    const double y = static_cast<double>(range) * std::sin(angle);

    addPlanarPoint(x, y, left_bins, right_bins);
  }

  return buildPathFromBins(scan_msg.header, output_frame, left_bins, right_bins);
}

CenterlineResult ScanPathBuilder::build(
  const sensor_msgs::msg::PointCloud2 & cloud_msg,
  const std::string & output_frame,
  double z_min,
  double z_max,
  std::size_t point_stride) const
{
  // 3D 点群を x-y 平面へ投影し、同じ中心線生成ロジックへ入力する。
  const std::size_t num_bins = computeBinCount();
  LateralBins left_bins(num_bins);
  LateralBins right_bins(num_bins);

  if (num_bins == 0) {
    return buildPathFromBins(cloud_msg.header, output_frame, left_bins, right_bins);
  }

  if (z_max < z_min) {
    std::swap(z_min, z_max);
  }

  const std::size_t stride = std::max<std::size_t>(point_stride, 1U);
  std::size_t point_index = 0;

  try {
    sensor_msgs::PointCloud2ConstIterator<float> iter_x(cloud_msg, "x");
    sensor_msgs::PointCloud2ConstIterator<float> iter_y(cloud_msg, "y");
    sensor_msgs::PointCloud2ConstIterator<float> iter_z(cloud_msg, "z");

    for (; iter_x != iter_x.end(); ++iter_x, ++iter_y, ++iter_z) {
      if ((point_index++ % stride) != 0U) {
        continue;
      }

      const double x = static_cast<double>(*iter_x);
      const double y = static_cast<double>(*iter_y);
      const double z = static_cast<double>(*iter_z);

      if (!std::isfinite(x) || !std::isfinite(y) || !std::isfinite(z)) {
        continue;
      }
      if (z < z_min || z > z_max) {
        continue;
      }

      addPlanarPoint(x, y, left_bins, right_bins);
    }
  } catch (const std::exception &) {
    // x/y/z フィールドを持たない点群は中心線生成対象外として空結果を返す。
  }

  return buildPathFromBins(cloud_msg.header, output_frame, left_bins, right_bins);
}

std::size_t ScanPathBuilder::computeBinCount() const
{
  if (forward_max_distance_ <= forward_min_distance_ || bin_size_ <= 0.0) {
    return 0;
  }

  return static_cast<std::size_t>(
    std::ceil((forward_max_distance_ - forward_min_distance_) / bin_size_));
}

void ScanPathBuilder::addPlanarPoint(
  double x,
  double y,
  LateralBins & left_bins,
  LateralBins & right_bins) const
{
  if (x < forward_min_distance_ || x > forward_max_distance_) {
    return;
  }
  if (std::fabs(y) > max_lateral_distance_) {
    return;
  }

  const std::size_t bin_index = static_cast<std::size_t>((x - forward_min_distance_) / bin_size_);
  if (bin_index >= left_bins.size()) {
    return;
  }

  if (y >= 0.0) {
    left_bins[bin_index].push_back(y);
  } else {
    right_bins[bin_index].push_back(y);
  }
}

CenterlineResult ScanPathBuilder::buildPathFromBins(
  const std_msgs::msg::Header & header,
  const std::string & output_frame,
  const LateralBins & left_bins,
  const LateralBins & right_bins) const
{
  CenterlineResult result;
  result.path.header.stamp = header.stamp;
  result.path.header.frame_id = output_frame.empty() ? header.frame_id : output_frame;

  std::size_t bins_with_missing_boundary = 0;
  std::size_t bins_with_any_boundary = 0;

  for (std::size_t bin_index = 0; bin_index < left_bins.size(); ++bin_index) {
    const bool has_left = left_bins[bin_index].size() >= min_points_per_side_;
    const bool has_right = right_bins[bin_index].size() >= min_points_per_side_;

    if (!has_left && !has_right) {
      // 両側境界点が不足しているビンは中心線生成対象外。
      continue;
    }

    bins_with_any_boundary++;
    if (!(has_left && has_right)) {
      bins_with_missing_boundary++;
    }

    const double x = forward_min_distance_ + (static_cast<double>(bin_index) + 0.5) * bin_size_;

    double center_y = 0.0;
    if (has_left && has_right) {
      // 左右両方の境界点があれば、その中間を中心線とする。
      center_y = 0.5 * (median(left_bins[bin_index]) + median(right_bins[bin_index]));
    } else if (has_left) {
      // 右境界点が欠落している場合は車線幅を仮定して中心線を推定。
      center_y = median(left_bins[bin_index]) - assumed_lane_half_width_;
    } else {
      // 左境界点が欠落している場合も同様に推定。
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
    // 2点未満の中心線では経路として不十分なので終了。
    result.missing_boundary_ratio = 1.0;
    return result;
  }

  for (std::size_t i = 0; i < result.path.poses.size(); ++i) {
    double yaw = 0.0;
    if (i + 1 < result.path.poses.size()) {
      const auto & current = result.path.poses[i].pose.position;
      const auto & next = result.path.poses[i + 1].pose.position;
      // 進行方向に沿って姿勢を計算する。
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
  // 経路の曲率代理値を計算して、警告スコア算出に使う。
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
