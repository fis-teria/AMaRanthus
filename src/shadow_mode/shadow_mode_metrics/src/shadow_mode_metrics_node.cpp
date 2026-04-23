#include "shadow_mode_metrics/shadow_mode_metrics_node.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <filesystem>
#include <iomanip>
#include <limits>
#include <sstream>

namespace shadow_mode_metrics
{

namespace
{

double clamp01(double value)
{
  return std::clamp(value, 0.0, 1.0);
}

}  // namespace

ShadowModeMetricsNode::ShadowModeMetricsNode()
: Node("shadow_mode_metrics")
{
  this->declare_parameter<std::string>("ego_speed_topic", "/shadow/ego/speed");
  this->declare_parameter<std::string>("ego_curvature_topic", "/shadow/ego/curvature");
  this->declare_parameter<std::string>(
    "virtual_steering_topic", "/shadow/virtual/steering_proxy");
  this->declare_parameter<std::string>("virtual_curvature_topic", "/shadow/virtual/curvature");
  this->declare_parameter<std::string>("virtual_warning_topic", "/shadow/virtual/warning_score");
  this->declare_parameter<double>("wheelbase", 2.7);
  this->declare_parameter<double>("publish_rate_hz", 10.0);
  this->declare_parameter<double>("max_signal_age_sec", 0.5);
  this->declare_parameter<double>("steering_delta_warn_rad", 0.2);
  this->declare_parameter<double>("curvature_delta_warn_inv_m", 0.1);
  this->declare_parameter<double>("steering_delta_weight", 0.5);
  this->declare_parameter<double>("curvature_delta_weight", 0.3);
  this->declare_parameter<double>("virtual_warning_weight", 0.2);
  this->declare_parameter<bool>("publish_invalid_summaries", false);
  this->declare_parameter<bool>("enable_csv_logging", false);
  this->declare_parameter<std::string>("csv_path", "Data/metrics/shadow_mode_metrics.csv");

  const auto ego_speed_topic = this->get_parameter("ego_speed_topic").as_string();
  const auto ego_curvature_topic = this->get_parameter("ego_curvature_topic").as_string();
  const auto virtual_steering_topic = this->get_parameter("virtual_steering_topic").as_string();
  const auto virtual_curvature_topic = this->get_parameter("virtual_curvature_topic").as_string();
  const auto virtual_warning_topic = this->get_parameter("virtual_warning_topic").as_string();
  wheelbase_ = this->get_parameter("wheelbase").as_double();
  publish_rate_hz_ = std::max(this->get_parameter("publish_rate_hz").as_double(), 0.1);
  max_signal_age_sec_ = std::max(this->get_parameter("max_signal_age_sec").as_double(), 0.0);
  steering_delta_warn_rad_ =
    std::max(this->get_parameter("steering_delta_warn_rad").as_double(), 1e-6);
  curvature_delta_warn_inv_m_ =
    std::max(this->get_parameter("curvature_delta_warn_inv_m").as_double(), 1e-6);
  steering_delta_weight_ = std::max(this->get_parameter("steering_delta_weight").as_double(), 0.0);
  curvature_delta_weight_ =
    std::max(this->get_parameter("curvature_delta_weight").as_double(), 0.0);
  virtual_warning_weight_ = std::max(this->get_parameter("virtual_warning_weight").as_double(), 0.0);
  publish_invalid_summaries_ = this->get_parameter("publish_invalid_summaries").as_bool();
  enable_csv_logging_ = this->get_parameter("enable_csv_logging").as_bool();
  csv_path_ = this->get_parameter("csv_path").as_string();

  ego_speed_sub_ = this->create_subscription<std_msgs::msg::Float32>(
    ego_speed_topic,
    20,
    std::bind(&ShadowModeMetricsNode::egoSpeedCallback, this, std::placeholders::_1));
  ego_curvature_sub_ = this->create_subscription<std_msgs::msg::Float32>(
    ego_curvature_topic,
    20,
    std::bind(&ShadowModeMetricsNode::egoCurvatureCallback, this, std::placeholders::_1));
  virtual_steering_sub_ = this->create_subscription<std_msgs::msg::Float32>(
    virtual_steering_topic,
    20,
    std::bind(&ShadowModeMetricsNode::virtualSteeringCallback, this, std::placeholders::_1));
  virtual_curvature_sub_ = this->create_subscription<std_msgs::msg::Float32>(
    virtual_curvature_topic,
    20,
    std::bind(&ShadowModeMetricsNode::virtualCurvatureCallback, this, std::placeholders::_1));
  virtual_warning_sub_ = this->create_subscription<std_msgs::msg::Float32>(
    virtual_warning_topic,
    20,
    std::bind(&ShadowModeMetricsNode::virtualWarningCallback, this, std::placeholders::_1));

  driver_steering_proxy_pub_ = this->create_publisher<std_msgs::msg::Float32>(
    "/shadow/metrics/driver_steering_proxy",
    10);
  steering_delta_pub_ =
    this->create_publisher<std_msgs::msg::Float32>("/shadow/metrics/steering_delta", 10);
  curvature_delta_pub_ =
    this->create_publisher<std_msgs::msg::Float32>("/shadow/metrics/curvature_delta", 10);
  intervention_score_pub_ =
    this->create_publisher<std_msgs::msg::Float32>("/shadow/metrics/intervention_score", 10);
  control_delta_pub_ = this->create_publisher<geometry_msgs::msg::Vector3Stamped>(
    "/shadow/metrics/control_delta",
    10);
  summary_pub_ = this->create_publisher<std_msgs::msg::String>("/shadow/metrics/summary", 10);

  const auto period = std::chrono::duration<double>(1.0 / publish_rate_hz_);
  timer_ = this->create_wall_timer(
    std::chrono::duration_cast<std::chrono::nanoseconds>(period),
    std::bind(&ShadowModeMetricsNode::timerCallback, this));
}

void ShadowModeMetricsNode::updateSignal(SignalSample & signal, float value)
{
  signal.value = static_cast<double>(value);
  signal.stamp = this->get_clock()->now();
  signal.valid = true;
}

void ShadowModeMetricsNode::egoSpeedCallback(const std_msgs::msg::Float32::SharedPtr msg)
{
  updateSignal(ego_speed_, msg->data);
}

void ShadowModeMetricsNode::egoCurvatureCallback(const std_msgs::msg::Float32::SharedPtr msg)
{
  updateSignal(ego_curvature_, msg->data);
}

void ShadowModeMetricsNode::virtualSteeringCallback(const std_msgs::msg::Float32::SharedPtr msg)
{
  updateSignal(virtual_steering_, msg->data);
}

void ShadowModeMetricsNode::virtualCurvatureCallback(const std_msgs::msg::Float32::SharedPtr msg)
{
  updateSignal(virtual_curvature_, msg->data);
}

void ShadowModeMetricsNode::virtualWarningCallback(const std_msgs::msg::Float32::SharedPtr msg)
{
  updateSignal(virtual_warning_, msg->data);
}

void ShadowModeMetricsNode::timerCallback()
{
  const auto now = this->get_clock()->now();
  const bool ready =
    isFresh(ego_speed_, now) &&
    isFresh(ego_curvature_, now) &&
    isFresh(virtual_steering_, now) &&
    isFresh(virtual_curvature_, now) &&
    isFresh(virtual_warning_, now);

  if (!ready) {
    if (publish_invalid_summaries_) {
      std_msgs::msg::String summary_msg;
      summary_msg.data = buildInvalidSummary(now);
      summary_pub_->publish(summary_msg);
    }
    return;
  }

  const double driver_steering_proxy = std::atan(wheelbase_ * ego_curvature_.value);
  const double steering_delta = virtual_steering_.value - driver_steering_proxy;
  const double curvature_delta = virtual_curvature_.value - ego_curvature_.value;

  const double raw_weight_sum =
    steering_delta_weight_ + curvature_delta_weight_ + virtual_warning_weight_;
  const double weight_sum = raw_weight_sum > 1e-9 ? raw_weight_sum : 1.0;
  const double intervention_score = clamp01(
    (steering_delta_weight_ * clamp01(std::fabs(steering_delta) / steering_delta_warn_rad_) +
    curvature_delta_weight_ * clamp01(std::fabs(curvature_delta) / curvature_delta_warn_inv_m_) +
    virtual_warning_weight_ * clamp01(virtual_warning_.value)) /
    weight_sum);

  std_msgs::msg::Float32 driver_steering_msg;
  driver_steering_msg.data = static_cast<float>(driver_steering_proxy);
  driver_steering_proxy_pub_->publish(driver_steering_msg);

  std_msgs::msg::Float32 steering_delta_msg;
  steering_delta_msg.data = static_cast<float>(steering_delta);
  steering_delta_pub_->publish(steering_delta_msg);

  std_msgs::msg::Float32 curvature_delta_msg;
  curvature_delta_msg.data = static_cast<float>(curvature_delta);
  curvature_delta_pub_->publish(curvature_delta_msg);

  std_msgs::msg::Float32 intervention_score_msg;
  intervention_score_msg.data = static_cast<float>(intervention_score);
  intervention_score_pub_->publish(intervention_score_msg);

  geometry_msgs::msg::Vector3Stamped control_delta_msg;
  control_delta_msg.header.stamp = now;
  control_delta_msg.header.frame_id = "shadow_metrics";
  control_delta_msg.vector.x = steering_delta;
  control_delta_msg.vector.y = curvature_delta;
  control_delta_msg.vector.z = intervention_score;
  control_delta_pub_->publish(control_delta_msg);

  std_msgs::msg::String summary_msg;
  summary_msg.data = buildValidSummary(
    now,
    driver_steering_proxy,
    steering_delta,
    curvature_delta,
    intervention_score);
  summary_pub_->publish(summary_msg);

  writeCsvRow(
    now,
    driver_steering_proxy,
    steering_delta,
    curvature_delta,
    intervention_score);
}

bool ShadowModeMetricsNode::isFresh(const SignalSample & signal, const rclcpp::Time & now) const
{
  return signal.valid && std::fabs(ageSec(signal, now)) <= max_signal_age_sec_;
}

double ShadowModeMetricsNode::ageSec(const SignalSample & signal, const rclcpp::Time & now) const
{
  if (!signal.valid) {
    return std::numeric_limits<double>::infinity();
  }
  return (now - signal.stamp).seconds();
}

double ShadowModeMetricsNode::maxObservedAgeSec(const rclcpp::Time & now) const
{
  return std::max(
    {
      std::fabs(ageSec(ego_speed_, now)),
      std::fabs(ageSec(ego_curvature_, now)),
      std::fabs(ageSec(virtual_steering_, now)),
      std::fabs(ageSec(virtual_curvature_, now)),
      std::fabs(ageSec(virtual_warning_, now)),
    });
}

std::string ShadowModeMetricsNode::buildInvalidSummary(const rclcpp::Time & now) const
{
  std::ostringstream oss;
  oss << std::fixed << std::setprecision(6)
      << "{\"valid\":false"
      << ",\"stamp_sec\":" << now.seconds()
      << ",\"reason\":\"missing_or_stale_signal\""
      << ",\"max_signal_age_sec\":" << max_signal_age_sec_
      << ",\"max_observed_age_sec\":" << maxObservedAgeSec(now)
      << "}";
  return oss.str();
}

std::string ShadowModeMetricsNode::buildValidSummary(
  const rclcpp::Time & now,
  double driver_steering_proxy,
  double steering_delta,
  double curvature_delta,
  double intervention_score) const
{
  std::ostringstream oss;
  oss << std::fixed << std::setprecision(6)
      << "{\"valid\":true"
      << ",\"stamp_sec\":" << now.seconds()
      << ",\"ego_speed_mps\":" << ego_speed_.value
      << ",\"ego_curvature_inv_m\":" << ego_curvature_.value
      << ",\"driver_steering_proxy_rad\":" << driver_steering_proxy
      << ",\"virtual_steering_rad\":" << virtual_steering_.value
      << ",\"steering_delta_rad\":" << steering_delta
      << ",\"virtual_curvature_inv_m\":" << virtual_curvature_.value
      << ",\"curvature_delta_inv_m\":" << curvature_delta
      << ",\"virtual_warning_score\":" << virtual_warning_.value
      << ",\"intervention_score\":" << intervention_score
      << ",\"max_observed_age_sec\":" << maxObservedAgeSec(now)
      << "}";
  return oss.str();
}

void ShadowModeMetricsNode::openCsvIfNeeded()
{
  if (!enable_csv_logging_ || csv_file_.is_open() || csv_open_attempted_) {
    return;
  }

  csv_open_attempted_ = true;

  try {
    const std::filesystem::path path(csv_path_);
    if (path.has_parent_path()) {
      std::filesystem::create_directories(path.parent_path());
    }

    const bool needs_header =
      !std::filesystem::exists(path) || std::filesystem::file_size(path) == 0U;
    csv_file_.open(path, std::ios::app);

    if (!csv_file_.is_open()) {
      RCLCPP_WARN(this->get_logger(), "Failed to open metrics CSV: %s", csv_path_.c_str());
      return;
    }

    if (needs_header) {
      csv_file_
        << "stamp_sec,ego_speed_mps,ego_curvature_inv_m,driver_steering_proxy_rad,"
        << "virtual_steering_rad,steering_delta_rad,virtual_curvature_inv_m,"
        << "curvature_delta_inv_m,virtual_warning_score,intervention_score,"
        << "max_observed_age_sec\n";
    }
  } catch (const std::exception & error) {
    RCLCPP_WARN(
      this->get_logger(),
      "Failed to prepare metrics CSV '%s': %s",
      csv_path_.c_str(),
      error.what());
  }
}

void ShadowModeMetricsNode::writeCsvRow(
  const rclcpp::Time & now,
  double driver_steering_proxy,
  double steering_delta,
  double curvature_delta,
  double intervention_score)
{
  openCsvIfNeeded();
  if (!csv_file_.is_open()) {
    return;
  }

  csv_file_ << std::fixed << std::setprecision(6)
            << now.seconds() << ','
            << ego_speed_.value << ','
            << ego_curvature_.value << ','
            << driver_steering_proxy << ','
            << virtual_steering_.value << ','
            << steering_delta << ','
            << virtual_curvature_.value << ','
            << curvature_delta << ','
            << virtual_warning_.value << ','
            << intervention_score << ','
            << maxObservedAgeSec(now) << '\n';
  csv_file_.flush();
}

}  // namespace shadow_mode_metrics

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<shadow_mode_metrics::ShadowModeMetricsNode>());
  rclcpp::shutdown();
  return 0;
}
