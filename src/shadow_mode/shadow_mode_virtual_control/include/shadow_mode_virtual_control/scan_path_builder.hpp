#ifndef SHADOW_MODE_VIRTUAL_CONTROL__SCAN_PATH_BUILDER_HPP_
#define SHADOW_MODE_VIRTUAL_CONTROL__SCAN_PATH_BUILDER_HPP_

#include <cstddef>
#include <string>
#include <vector>

#include "geometry_msgs/msg/pose_stamped.hpp"
#include "nav_msgs/msg/path.hpp"
#include "sensor_msgs/msg/laser_scan.hpp"

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
  ScanPathBuilder(
    double forward_min_distance,
    double forward_max_distance,
    double bin_size,
    double max_lateral_distance,
    double assumed_lane_half_width,
    std::size_t min_points_per_side);

  CenterlineResult build(
    const sensor_msgs::msg::LaserScan & scan_msg,
    const std::string & output_frame) const;

private:
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
