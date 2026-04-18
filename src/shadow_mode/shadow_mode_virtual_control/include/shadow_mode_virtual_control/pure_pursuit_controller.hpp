#ifndef SHADOW_MODE_VIRTUAL_CONTROL__PURE_PURSUIT_CONTROLLER_HPP_
#define SHADOW_MODE_VIRTUAL_CONTROL__PURE_PURSUIT_CONTROLLER_HPP_

#include "nav_msgs/msg/path.hpp"

namespace shadow_mode_virtual_control
{

struct PurePursuitResult
{
  double steering_rad {0.0};
  double curvature_inv_m {0.0};
  bool has_target {false};
};

class PurePursuitController
{
public:
  PurePursuitController(double wheelbase, double lookahead_distance, double max_steering_rad);

  PurePursuitResult compute(const nav_msgs::msg::Path & path) const;

private:
  double wheelbase_;
  double lookahead_distance_;
  double max_steering_rad_;
};

}  // namespace shadow_mode_virtual_control

#endif  // SHADOW_MODE_VIRTUAL_CONTROL__PURE_PURSUIT_CONTROLLER_HPP_
