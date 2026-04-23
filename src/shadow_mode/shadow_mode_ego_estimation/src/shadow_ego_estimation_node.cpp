#include "shadow_mode_ego_estimation/shadow_ego_estimation_node.hpp"

#include <memory>
#include <string>

#include "geometry_msgs/msg/point.hpp"
#include "std_msgs/msg/float32.hpp"
#include "visualization_msgs/msg/marker.hpp"
#include "visualization_msgs/msg/marker_array.hpp"

namespace shadow_mode_ego_estimation
{

ShadowEgoEstimationNode::ShadowEgoEstimationNode()
: Node("shadow_ego_estimation")
{
  // ノードパラメータを宣言し、動的に設定を読み込む。
  this->declare_parameter<std::string>("input_odom_topic", "/Odometry");
  this->declare_parameter<std::string>("output_frame", "");
  this->declare_parameter<int>("path_buffer_size", 200);
  this->declare_parameter<double>("min_dt", 0.01);
  this->declare_parameter<double>("min_speed_for_curvature", 0.5);
  this->declare_parameter<double>("speed_smoothing_gain", 0.2);
  this->declare_parameter<double>("yaw_rate_smoothing_gain", 0.2);
  this->declare_parameter<bool>("publish_debug_markers", true);

  const auto input_odom_topic = this->get_parameter("input_odom_topic").as_string();
  output_frame_ = this->get_parameter("output_frame").as_string();
  const auto path_buffer_size = this->get_parameter("path_buffer_size").as_int();
  const auto min_dt = this->get_parameter("min_dt").as_double();
  const auto min_speed_for_curvature =
    this->get_parameter("min_speed_for_curvature").as_double();
  const auto speed_smoothing_gain =
    this->get_parameter("speed_smoothing_gain").as_double();
  const auto yaw_rate_smoothing_gain =
    this->get_parameter("yaw_rate_smoothing_gain").as_double();
  publish_debug_markers_ = this->get_parameter("publish_debug_markers").as_bool();

  // EgoMotionEstimator を初期化し、過去 odometry のバッファと平滑化設定を構成する。
  estimator_ = std::make_unique<EgoMotionEstimator>(
    static_cast<std::size_t>(path_buffer_size),
    min_dt,
    min_speed_for_curvature,
    speed_smoothing_gain,
    yaw_rate_smoothing_gain);

  odom_sub_ = this->create_subscription<nav_msgs::msg::Odometry>(
    input_odom_topic,
    20,
    std::bind(&ShadowEgoEstimationNode::odomCallback, this, std::placeholders::_1));

  ego_path_pub_ = this->create_publisher<nav_msgs::msg::Path>("/shadow/ego/path", 10);
  ego_speed_pub_ = this->create_publisher<std_msgs::msg::Float32>("/shadow/ego/speed", 10);
  ego_yaw_rate_pub_ =
    this->create_publisher<std_msgs::msg::Float32>("/shadow/ego/yaw_rate", 10);
  ego_curvature_pub_ =
    this->create_publisher<std_msgs::msg::Float32>("/shadow/ego/curvature", 10);

  if (publish_debug_markers_) {
    ego_debug_markers_pub_ = this->create_publisher<visualization_msgs::msg::MarkerArray>(
      "/shadow/ego/debug_markers", 10);
  }
}

void ShadowEgoEstimationNode::odomCallback(const nav_msgs::msg::Odometry::SharedPtr msg)
{
  // インポートした odometry から ego motion を推定し、各種トピックを公開する。
  const auto state = estimator_->update(*msg);
  const auto frame_id = output_frame_.empty() ? msg->header.frame_id : output_frame_;

  auto path = estimator_->buildPath(frame_id);
  ego_path_pub_->publish(path);

  // 推定結果をそれぞれのシャドウ出力トピックに変換して公開する。
  std_msgs::msg::Float32 speed_msg;
  speed_msg.data = static_cast<float>(state.speed_mps);
  ego_speed_pub_->publish(speed_msg);

  std_msgs::msg::Float32 yaw_rate_msg;
  yaw_rate_msg.data = static_cast<float>(state.yaw_rate_rps);
  ego_yaw_rate_pub_->publish(yaw_rate_msg);

  std_msgs::msg::Float32 curvature_msg;
  curvature_msg.data = static_cast<float>(state.curvature_inv_m);
  ego_curvature_pub_->publish(curvature_msg);

  if (publish_debug_markers_ && ego_debug_markers_pub_ != nullptr) {
    // 生成した中心線を RViz で可視化するために MarkerArray を作成する。
    visualization_msgs::msg::MarkerArray marker_array;
    visualization_msgs::msg::Marker marker;
    marker.header = path.header;
    marker.ns = "shadow_ego_path";
    marker.id = 0;
    marker.type = visualization_msgs::msg::Marker::LINE_STRIP;
    marker.action = visualization_msgs::msg::Marker::ADD;
    marker.scale.x = 0.15;
    marker.color.a = 1.0F;
    marker.color.r = 0.1F;
    marker.color.g = 0.8F;
    marker.color.b = 0.2F;

    for (const auto & pose_stamped : path.poses) {
      geometry_msgs::msg::Point point;
      point.x = pose_stamped.pose.position.x;
      point.y = pose_stamped.pose.position.y;
      point.z = pose_stamped.pose.position.z;
      marker.points.push_back(point);
    }

    marker_array.markers.push_back(marker);
    ego_debug_markers_pub_->publish(marker_array);
  }
}

}  // namespace shadow_mode_ego_estimation

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<shadow_mode_ego_estimation::ShadowEgoEstimationNode>());
  rclcpp::shutdown();
  return 0;
}
