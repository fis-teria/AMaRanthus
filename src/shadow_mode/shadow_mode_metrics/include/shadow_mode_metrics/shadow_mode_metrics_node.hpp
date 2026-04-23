#ifndef SHADOW_MODE_METRICS__SHADOW_MODE_METRICS_NODE_HPP_
#define SHADOW_MODE_METRICS__SHADOW_MODE_METRICS_NODE_HPP_

#include <fstream>
#include <string>

#include "geometry_msgs/msg/vector3_stamped.hpp"
#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/float32.hpp"
#include "std_msgs/msg/string.hpp"

namespace shadow_mode_metrics
{

/// Ego motion から導いた driver proxy と仮想制御を同じ時刻軸で比較するノード。
class ShadowModeMetricsNode : public rclcpp::Node
{
public:
  ShadowModeMetricsNode();

private:
  struct SignalSample
  {
    double value {0.0};
    rclcpp::Time stamp;
    bool valid {false};
  };

  void updateSignal(SignalSample & signal, float value);
  void egoSpeedCallback(const std_msgs::msg::Float32::SharedPtr msg);
  void egoCurvatureCallback(const std_msgs::msg::Float32::SharedPtr msg);
  void virtualSteeringCallback(const std_msgs::msg::Float32::SharedPtr msg);
  void virtualCurvatureCallback(const std_msgs::msg::Float32::SharedPtr msg);
  void virtualWarningCallback(const std_msgs::msg::Float32::SharedPtr msg);
  void timerCallback();

  bool isFresh(const SignalSample & signal, const rclcpp::Time & now) const;
  double ageSec(const SignalSample & signal, const rclcpp::Time & now) const;
  double maxObservedAgeSec(const rclcpp::Time & now) const;
  std::string buildInvalidSummary(const rclcpp::Time & now) const;
  std::string buildValidSummary(
    const rclcpp::Time & now,
    double driver_steering_proxy,
    double steering_delta,
    double curvature_delta,
    double intervention_score) const;
  void openCsvIfNeeded();
  void writeCsvRow(
    const rclcpp::Time & now,
    double driver_steering_proxy,
    double steering_delta,
    double curvature_delta,
    double intervention_score);

  double wheelbase_ {2.7};
  double publish_rate_hz_ {10.0};
  double max_signal_age_sec_ {0.5};
  double steering_delta_warn_rad_ {0.2};
  double curvature_delta_warn_inv_m_ {0.1};
  double steering_delta_weight_ {0.5};
  double curvature_delta_weight_ {0.3};
  double virtual_warning_weight_ {0.2};
  bool publish_invalid_summaries_ {false};
  bool enable_csv_logging_ {false};
  std::string csv_path_ {"Data/metrics/shadow_mode_metrics.csv"};

  SignalSample ego_speed_;
  SignalSample ego_curvature_;
  SignalSample virtual_steering_;
  SignalSample virtual_curvature_;
  SignalSample virtual_warning_;

  rclcpp::Subscription<std_msgs::msg::Float32>::SharedPtr ego_speed_sub_;
  rclcpp::Subscription<std_msgs::msg::Float32>::SharedPtr ego_curvature_sub_;
  rclcpp::Subscription<std_msgs::msg::Float32>::SharedPtr virtual_steering_sub_;
  rclcpp::Subscription<std_msgs::msg::Float32>::SharedPtr virtual_curvature_sub_;
  rclcpp::Subscription<std_msgs::msg::Float32>::SharedPtr virtual_warning_sub_;

  rclcpp::Publisher<std_msgs::msg::Float32>::SharedPtr driver_steering_proxy_pub_;
  rclcpp::Publisher<std_msgs::msg::Float32>::SharedPtr steering_delta_pub_;
  rclcpp::Publisher<std_msgs::msg::Float32>::SharedPtr curvature_delta_pub_;
  rclcpp::Publisher<std_msgs::msg::Float32>::SharedPtr intervention_score_pub_;
  rclcpp::Publisher<geometry_msgs::msg::Vector3Stamped>::SharedPtr control_delta_pub_;
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr summary_pub_;

  rclcpp::TimerBase::SharedPtr timer_;

  std::ofstream csv_file_;
  bool csv_open_attempted_ {false};
};

}  // namespace shadow_mode_metrics

#endif  // SHADOW_MODE_METRICS__SHADOW_MODE_METRICS_NODE_HPP_
