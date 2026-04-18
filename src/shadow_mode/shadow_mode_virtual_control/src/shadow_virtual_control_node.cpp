#include "shadow_mode_virtual_control/shadow_virtual_control_node.hpp"

#include <algorithm>
#include <memory>
#include <string>

#include "geometry_msgs/msg/point.hpp"
#include "visualization_msgs/msg/marker.hpp"

namespace shadow_mode_virtual_control
{

ShadowVirtualControlNode::ShadowVirtualControlNode()
: Node("shadow_virtual_control")
{
  this->declare_parameter<std::string>("input_scan_topic", "/livox/lane_detection/scan");
  this->declare_parameter<std::string>("output_frame", "");
  this->declare_parameter<double>("wheelbase", 2.7);
  this->declare_parameter<double>("lookahead_distance", 6.0);
  this->declare_parameter<double>("max_steering_rad", 0.6);
  this->declare_parameter<double>("forward_min_distance", 2.0);
  this->declare_parameter<double>("forward_max_distance", 20.0);
  this->declare_parameter<double>("bin_size", 1.0);
  this->declare_parameter<double>("max_lateral_distance", 8.0);
  this->declare_parameter<double>("assumed_lane_half_width", 1.75);
  this->declare_parameter<int>("min_points_per_side", 1);
  this->declare_parameter<bool>("publish_debug_markers", true);
  this->declare_parameter<double>("warning_missing_boundary_weight", 0.7);
  this->declare_parameter<double>("warning_curvature_weight", 0.3);

  const auto input_scan_topic = this->get_parameter("input_scan_topic").as_string();
  output_frame_ = this->get_parameter("output_frame").as_string();
  const auto wheelbase = this->get_parameter("wheelbase").as_double();
  const auto lookahead_distance = this->get_parameter("lookahead_distance").as_double();
  const auto max_steering_rad = this->get_parameter("max_steering_rad").as_double();
  const auto forward_min_distance = this->get_parameter("forward_min_distance").as_double();
  const auto forward_max_distance = this->get_parameter("forward_max_distance").as_double();
  const auto bin_size = this->get_parameter("bin_size").as_double();
  const auto max_lateral_distance = this->get_parameter("max_lateral_distance").as_double();
  const auto assumed_lane_half_width = this->get_parameter("assumed_lane_half_width").as_double();
  const auto min_points_per_side = this->get_parameter("min_points_per_side").as_int();
  publish_debug_markers_ = this->get_parameter("publish_debug_markers").as_bool();
  warning_missing_boundary_weight_ =
    this->get_parameter("warning_missing_boundary_weight").as_double();
  warning_curvature_weight_ = this->get_parameter("warning_curvature_weight").as_double();

  path_builder_ = std::make_unique<ScanPathBuilder>(
    forward_min_distance,
    forward_max_distance,
    bin_size,
    max_lateral_distance,
    assumed_lane_half_width,
    static_cast<std::size_t>(min_points_per_side));

  controller_ = std::make_unique<PurePursuitController>(
    wheelbase,
    lookahead_distance,
    max_steering_rad);

  scan_sub_ = this->create_subscription<sensor_msgs::msg::LaserScan>(
    input_scan_topic,
    rclcpp::SensorDataQoS(),
    std::bind(&ShadowVirtualControlNode::scanCallback, this, std::placeholders::_1));

  virtual_path_pub_ = this->create_publisher<nav_msgs::msg::Path>("/shadow/virtual/path", 10);
  virtual_steering_pub_ =
    this->create_publisher<std_msgs::msg::Float32>("/shadow/virtual/steering_proxy", 10);
  virtual_curvature_pub_ =
    this->create_publisher<std_msgs::msg::Float32>("/shadow/virtual/curvature", 10);
  warning_score_pub_ =
    this->create_publisher<std_msgs::msg::Float32>("/shadow/virtual/warning_score", 10);

  if (publish_debug_markers_) {
    debug_markers_pub_ = this->create_publisher<visualization_msgs::msg::MarkerArray>(
      "/shadow/virtual/debug_markers", 10);
  }
}

void ShadowVirtualControlNode::scanCallback(const sensor_msgs::msg::LaserScan::SharedPtr msg)
{
  const auto centerline = path_builder_->build(*msg, output_frame_);
  virtual_path_pub_->publish(centerline.path);

  const auto control = controller_->compute(centerline.path);

  std_msgs::msg::Float32 steering_msg;
  steering_msg.data = static_cast<float>(control.steering_rad);
  virtual_steering_pub_->publish(steering_msg);

  std_msgs::msg::Float32 curvature_msg;
  curvature_msg.data = static_cast<float>(control.curvature_inv_m);
  virtual_curvature_pub_->publish(curvature_msg);

  const double curvature_component = std::min(centerline.path_curvature_proxy, 1.0);
  const double warning_score = std::clamp(
    warning_missing_boundary_weight_ * centerline.missing_boundary_ratio +
    warning_curvature_weight_ * curvature_component,
    0.0,
    1.0);

  std_msgs::msg::Float32 warning_msg;
  warning_msg.data = static_cast<float>(warning_score);
  warning_score_pub_->publish(warning_msg);

  if (publish_debug_markers_ && debug_markers_pub_ != nullptr) {
    debug_markers_pub_->publish(
      buildDebugMarkers(
        centerline.path,
        centerline.path.header.frame_id,
        msg->header.stamp));
  }
}

visualization_msgs::msg::MarkerArray ShadowVirtualControlNode::buildDebugMarkers(
  const nav_msgs::msg::Path & path,
  const std::string & frame_id,
  const rclcpp::Time & stamp) const
{
  visualization_msgs::msg::MarkerArray marker_array;

  visualization_msgs::msg::Marker path_marker;
  path_marker.header.frame_id = frame_id;
  path_marker.header.stamp = stamp;
  path_marker.ns = "shadow_virtual_path";
  path_marker.id = 0;
  path_marker.type = visualization_msgs::msg::Marker::LINE_STRIP;
  path_marker.action = visualization_msgs::msg::Marker::ADD;
  path_marker.scale.x = 0.15;
  path_marker.color.a = 1.0F;
  path_marker.color.r = 0.1F;
  path_marker.color.g = 0.5F;
  path_marker.color.b = 1.0F;

  for (const auto & pose_stamped : path.poses) {
    geometry_msgs::msg::Point point;
    point.x = pose_stamped.pose.position.x;
    point.y = pose_stamped.pose.position.y;
    point.z = pose_stamped.pose.position.z;
    path_marker.points.push_back(point);
  }

  marker_array.markers.push_back(path_marker);
  return marker_array;
}

}  // namespace shadow_mode_virtual_control

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<shadow_mode_virtual_control::ShadowVirtualControlNode>());
  rclcpp::shutdown();
  return 0;
}
