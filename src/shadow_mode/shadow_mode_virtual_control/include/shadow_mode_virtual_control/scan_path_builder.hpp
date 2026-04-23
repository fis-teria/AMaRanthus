#ifndef SHADOW_MODE_VIRTUAL_CONTROL__SCAN_PATH_BUILDER_HPP_
#define SHADOW_MODE_VIRTUAL_CONTROL__SCAN_PATH_BUILDER_HPP_

#include <cstddef>
#include <string>
#include <vector>

#include "geometry_msgs/msg/pose_stamped.hpp"
#include "nav_msgs/msg/path.hpp"
#include "sensor_msgs/msg/laser_scan.hpp"
#include "sensor_msgs/msg/point_cloud2.hpp"
#include "std_msgs/msg/header.hpp"

namespace shadow_mode_virtual_control
{

struct CenterlineResult
{
  nav_msgs::msg::Path path;
  double missing_boundary_ratio {1.0};
  double path_curvature_proxy {0.0};
  bool has_path {false};
};

class ScanPathBuilder
{
public:
  /// LiDAR スキャンデータから中心線経路を構築するクラス。
  /// 左右境界線の有無に応じて中心線を補間する。
  ScanPathBuilder(
    double forward_min_distance,
    double forward_max_distance,
    double bin_size,
    double max_lateral_distance,
    double assumed_lane_half_width,
    std::size_t min_points_per_side);

  /// LaserScan を元に中心線経路を作成する。
  /// 出力フレームは必要に応じて書き換えられる。
  CenterlineResult build(
    const sensor_msgs::msg::LaserScan & scan_msg,
    const std::string & output_frame) const;

  /// 3D PointCloud2 を地面平面へ投影し、中心線経路を作成する。
  /// z フィルタと stride により、raw 3D LiDAR 入力でも負荷を調整できる。
  CenterlineResult build(
    const sensor_msgs::msg::PointCloud2 & cloud_msg,
    const std::string & output_frame,
    double z_min,
    double z_max,
    std::size_t point_stride) const;

private:
  using LateralBins = std::vector<std::vector<double>>;

  std::size_t computeBinCount() const;
  void addPlanarPoint(double x, double y, LateralBins & left_bins, LateralBins & right_bins) const;
  CenterlineResult buildPathFromBins(
    const std_msgs::msg::Header & header,
    const std::string & output_frame,
    const LateralBins & left_bins,
    const LateralBins & right_bins) const;
  static double median(std::vector<double> values);
  static double normalizeAngle(double angle_rad);
  static double computeCurvatureProxy(
    const std::vector<geometry_msgs::msg::PoseStamped> & poses);

  double forward_min_distance_;
  double forward_max_distance_;
  double bin_size_;
  double max_lateral_distance_;
  double assumed_lane_half_width_;
  std::size_t min_points_per_side_;
};

}  // namespace shadow_mode_virtual_control

#endif  // SHADOW_MODE_VIRTUAL_CONTROL__SCAN_PATH_BUILDER_HPP_
