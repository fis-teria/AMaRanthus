#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <memory>
#include <optional>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>
#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/image_encodings.hpp>
#include <sensor_msgs/msg/compressed_image.hpp>
#include <sensor_msgs/msg/camera_info.hpp>
#include <sensor_msgs/msg/image.hpp>
#include <std_msgs/msg/string.hpp>
#include <nav_msgs/msg/path.hpp>
#include <tf2/exceptions.h>
#include <tf2_ros/buffer.h>
#include <tf2_ros/transform_listener.h>
#include <yolo_msgs/msg/detection_array.hpp>

namespace
{

double stamp_to_sec(const builtin_interfaces::msg::Time & stamp)
{
  return static_cast<double>(stamp.sec) + static_cast<double>(stamp.nanosec) * 1.0e-9;
}

std::string json_escape(const std::string & value)
{
  std::ostringstream out;
  for (const char ch : value) {
    switch (ch) {
      case '\\':
        out << "\\\\";
        break;
      case '"':
        out << "\\\"";
        break;
      case '\n':
        out << "\\n";
        break;
      case '\r':
        out << "\\r";
        break;
      case '\t':
        out << "\\t";
        break;
      default:
        out << ch;
        break;
    }
  }
  return out.str();
}

std::vector<std::string> unique_topics(
  const std::string & primary, const std::vector<std::string> & fallback_topics)
{
  std::vector<std::string> topics;
  if (!primary.empty()) {
    topics.push_back(primary);
  }
  for (const auto & topic : fallback_topics) {
    if (topic.empty()) {
      continue;
    }
    if (std::find(topics.begin(), topics.end(), topic) == topics.end()) {
      topics.push_back(topic);
    }
  }
  return topics;
}

std::vector<int64_t> declare_color(
  rclcpp::Node & node, const std::string & name, const std::vector<int64_t> & fallback)
{
  auto value = node.declare_parameter<std::vector<int64_t>>(name, fallback);
  if (value.size() < 3) {
    return fallback;
  }
  for (auto & channel : value) {
    channel = std::clamp<int64_t>(channel, 0, 255);
  }
  return value;
}

struct CameraModel
{
  double fx;
  double fy;
  double cx;
  double cy;
  int width;
  int height;
};

struct CameraTranslation
{
  double x;
  double y;
  double z;
  std::string source;
};

struct ProjectedPathSample
{
  cv::Point center;
  std::optional<cv::Point> left;
  std::optional<cv::Point> right;
  double depth_m;
};

struct OverlayImage
{
  cv::Mat image_rgb;
  sensor_msgs::msg::Image::ConstSharedPtr source;
  double scale_x;
  double scale_y;
  std::string source_encoding;
};

struct OverlayTimingMs
{
  double total{0.0};
  double overlay_convert{0.0};
  double model_input{0.0};
  double tf_lookup{0.0};
  double project{0.0};
  double yolo{0.0};
  double draw{0.0};
  double image_publish{0.0};
  double jpeg_publish{0.0};
};

}  // namespace

class E2EPathOverlayNode : public rclcpp::Node
{
public:
  E2EPathOverlayNode()
  : Node("e2e_path_overlay"),
    tf_buffer_(this->get_clock()),
    tf_listener_(tf_buffer_)
  {
    image_topic_ = declare_parameter<std::string>("image_topic", "/sensing/camera/camera0/image_rect_color");
    image_fallback_topics_ = declare_parameter<std::vector<std::string>>(
      "image_fallback_topics", {"/sensing/camera/camera0/image_rect_color", "/image_rect_color"});
    camera_info_topic_ = declare_parameter<std::string>(
      "camera_info_topic", "/sensing/camera/camera0/camera_info");
    path_topic_ = declare_parameter<std::string>("path_topic", "/shadow/e2e/path");
    yolo_detections_topic_ = declare_parameter<std::string>("yolo_detections_topic", "/yolo/tracking");
    output_image_topic_ = declare_parameter<std::string>("output_image_topic", "/shadow/e2e/overlay_image");
    output_compressed_image_topic_ = declare_parameter<std::string>(
      "output_compressed_image_topic", "/shadow/e2e/overlay_image/compressed");
    output_status_topic_ = declare_parameter<std::string>("output_status_topic", "/shadow/e2e/overlay_status");
    model_input_image_topic_ = declare_parameter<std::string>(
      "model_input_image_topic", "/shadow/e2e/model_input_image");

    use_tf_translation_ = declare_parameter<bool>("use_tf_translation", true);
    camera_x_m_ = declare_parameter<double>("camera_x_m", 1.2);
    camera_y_m_ = declare_parameter<double>("camera_y_m", 0.1);
    camera_z_m_ = declare_parameter<double>("camera_z_m", 1.35);
    min_depth_m_ = declare_parameter<double>("min_depth_m", 0.5);
    max_depth_m_ = declare_parameter<double>("max_depth_m", 80.0);
    path_ribbon_width_m_ = std::max(0.1, declare_parameter<double>("path_ribbon_width_m", 2.8));
    path_ribbon_alpha_near_ = std::clamp(declare_parameter<double>("path_ribbon_alpha_near", 0.62), 0.0, 1.0);
    path_ribbon_alpha_far_ = std::clamp(declare_parameter<double>("path_ribbon_alpha_far", 0.22), 0.0, 1.0);
    line_width_px_ = std::max<int>(1, static_cast<int>(declare_parameter<int64_t>("line_width_px", 5)));
    point_radius_px_ = std::max<int>(1, static_cast<int>(declare_parameter<int64_t>("point_radius_px", 3)));
    path_edge_width_px_ = std::max<int>(0, static_cast<int>(declare_parameter<int64_t>("path_edge_width_px", 2)));
    draw_waypoints_ = declare_parameter<bool>("draw_waypoints", false);
    draw_yolo_boxes_ = declare_parameter<bool>("draw_yolo_boxes", true);
    yolo_min_score_ = declare_parameter<double>("yolo_min_score", 0.25);
    yolo_box_width_px_ = std::max<int>(1, static_cast<int>(declare_parameter<int64_t>("yolo_box_width_px", 3)));
    stale_path_timeout_sec_ = declare_parameter<double>("stale_path_timeout_sec", 1.0);
    stale_yolo_timeout_sec_ = declare_parameter<double>("stale_yolo_timeout_sec", 1.0);
    stale_camera_info_timeout_sec_ = declare_parameter<double>("stale_camera_info_timeout_sec", 2.0);
    output_max_edge_px_ = std::max<int>(0, static_cast<int>(declare_parameter<int64_t>("output_max_edge_px", 640)));
    model_input_width_px_ = std::max<int>(0, static_cast<int>(declare_parameter<int64_t>("model_input_width_px", 1152)));
    model_input_height_px_ = std::max<int>(0, static_cast<int>(declare_parameter<int64_t>("model_input_height_px", 384)));
    output_compressed_jpeg_quality_ = std::clamp<int>(
      static_cast<int>(declare_parameter<int64_t>("output_compressed_jpeg_quality", 80)), 1, 100);
    publish_status_every_frame_ = declare_parameter<bool>("publish_status_every_frame", true);

    const auto ribbon_color = declare_color(*this, "path_ribbon_color_rgb", {0, 210, 120});
    const auto edge_color = declare_color(*this, "path_edge_color_rgb", {180, 255, 210});
    const auto line_color = declare_color(*this, "line_color_rgb", {0, 255, 80});
    const auto yolo_color = declare_color(*this, "yolo_box_color_rgb", {255, 220, 0});
    path_ribbon_color_rgb_ = cv::Scalar(ribbon_color[0], ribbon_color[1], ribbon_color[2]);
    path_edge_color_rgb_ = cv::Scalar(edge_color[0], edge_color[1], edge_color[2]);
    line_color_rgb_ = cv::Scalar(line_color[0], line_color[1], line_color[2]);
    yolo_box_color_rgb_ = cv::Scalar(yolo_color[0], yolo_color[1], yolo_color[2]);

    image_topics_ = unique_topics(image_topic_, image_fallback_topics_);
    for (const auto & topic : image_topics_) {
      image_subs_.push_back(create_subscription<sensor_msgs::msg::Image>(
        topic, rclcpp::SensorDataQoS(),
        std::bind(&E2EPathOverlayNode::image_callback, this, std::placeholders::_1)));
    }
    camera_info_sub_ = create_subscription<sensor_msgs::msg::CameraInfo>(
      camera_info_topic_, rclcpp::SensorDataQoS(),
      std::bind(&E2EPathOverlayNode::camera_info_callback, this, std::placeholders::_1));
    path_sub_ = create_subscription<nav_msgs::msg::Path>(
      path_topic_, 10, std::bind(&E2EPathOverlayNode::path_callback, this, std::placeholders::_1));
    yolo_sub_ = create_subscription<yolo_msgs::msg::DetectionArray>(
      yolo_detections_topic_, rclcpp::SensorDataQoS(),
      std::bind(&E2EPathOverlayNode::yolo_callback, this, std::placeholders::_1));

    overlay_pub_ = create_publisher<sensor_msgs::msg::Image>(output_image_topic_, rclcpp::SensorDataQoS());
    if (!output_compressed_image_topic_.empty()) {
      compressed_overlay_pub_ = create_publisher<sensor_msgs::msg::CompressedImage>(
        output_compressed_image_topic_, rclcpp::SensorDataQoS());
    }
    if (!model_input_image_topic_.empty() && model_input_width_px_ > 0 && model_input_height_px_ > 0) {
      model_input_pub_ = create_publisher<sensor_msgs::msg::Image>(
        model_input_image_topic_, rclcpp::SensorDataQoS());
    }
    status_pub_ = create_publisher<std_msgs::msg::String>(output_status_topic_, 10);

    RCLCPP_INFO(
      get_logger(),
      "e2e_path_overlay C++ started images=%zu path=%s yolo=%s output_max_edge_px=%d compressed=%s model_input=%s %dx%d",
      image_topics_.size(), path_topic_.c_str(), yolo_detections_topic_.c_str(), output_max_edge_px_,
      output_compressed_image_topic_.c_str(), model_input_image_topic_.c_str(),
      model_input_width_px_, model_input_height_px_);
  }

private:
  void camera_info_callback(const sensor_msgs::msg::CameraInfo::SharedPtr msg)
  {
    latest_camera_info_ = msg;
    latest_camera_info_received_at_ = now();
  }

  void path_callback(const nav_msgs::msg::Path::SharedPtr msg)
  {
    latest_path_ = msg;
    latest_path_received_at_ = now();
  }

  void yolo_callback(const yolo_msgs::msg::DetectionArray::SharedPtr msg)
  {
    latest_yolo_detections_ = msg;
    latest_yolo_received_at_ = now();
  }

  void image_callback(const sensor_msgs::msg::Image::ConstSharedPtr msg)
  {
    const auto callback_start = std::chrono::steady_clock::now();
    const auto current_time = now();
    const auto overlay = make_overlay_image(msg);
    const auto after_overlay = std::chrono::steady_clock::now();
    if (!overlay) {
      OverlayTimingMs timing;
      timing.overlay_convert = elapsed_ms(callback_start, after_overlay);
      timing.total = timing.overlay_convert;
      publish_status(
        current_time, msg, 0, 0, 0, "unsupported_encoding:" + msg->encoding,
        std::nullopt, 0, 0, timing);
      return;
    }
    const double model_input_ms = publish_model_input_image(msg);

    if (!is_fresh(latest_camera_info_received_at_, current_time, stale_camera_info_timeout_sec_) ||
      !is_fresh(latest_path_received_at_, current_time, stale_path_timeout_sec_))
    {
      std::string missing;
      if (!is_fresh(latest_camera_info_received_at_, current_time, stale_camera_info_timeout_sec_)) {
        missing = "camera_info";
      }
      if (!is_fresh(latest_path_received_at_, current_time, stale_path_timeout_sec_)) {
        if (!missing.empty()) {
          missing += ",";
        }
        missing += "path";
      }
      OverlayTimingMs timing;
      timing.overlay_convert = elapsed_ms(callback_start, after_overlay);
      timing.model_input = model_input_ms;
      timing.total = elapsed_ms(callback_start, std::chrono::steady_clock::now());
      publish_status(
        current_time, msg, 0, 0, 0, "missing_or_stale:" + missing, std::nullopt,
        overlay->image_rgb.cols, overlay->image_rgb.rows, timing);
      return;
    }

    const auto before_tf = std::chrono::steady_clock::now();
    auto camera_translation = get_camera_translation(*latest_path_, *msg);
    const auto after_tf = std::chrono::steady_clock::now();
    const auto camera_model = camera_model_from_info(*latest_camera_info_, *msg, overlay->scale_x, overlay->scale_y);
    const auto projected_points = project_path(*latest_path_, camera_model, camera_translation);
    const auto after_project = std::chrono::steady_clock::now();
    auto yolo_boxes = fresh_yolo_boxes(current_time, *msg, overlay->scale_x, overlay->scale_y);
    const auto after_yolo = std::chrono::steady_clock::now();

    cv::Mat drawn = overlay->image_rgb.clone();
    draw_path(drawn, projected_points);
    draw_boxes(drawn, yolo_boxes);
    const auto after_draw = std::chrono::steady_clock::now();

    auto output = std::make_unique<sensor_msgs::msg::Image>();
    output->header = msg->header;
    output->height = static_cast<uint32_t>(drawn.rows);
    output->width = static_cast<uint32_t>(drawn.cols);
    output->encoding = sensor_msgs::image_encodings::RGB8;
    output->is_bigendian = 0;
    output->step = static_cast<uint32_t>(drawn.cols * 3);
    output->data.assign(drawn.datastart, drawn.dataend);
    overlay_pub_->publish(std::move(output));
    const auto after_image_publish = std::chrono::steady_clock::now();
    const double jpeg_publish_ms = publish_compressed_overlay(drawn, msg->header);
    const auto after_jpeg_publish = std::chrono::steady_clock::now();

    const int drawn_segments = count_drawn_segments(projected_points);
    if (publish_status_every_frame_) {
      OverlayTimingMs timing;
      timing.total = elapsed_ms(callback_start, after_jpeg_publish);
      timing.overlay_convert = elapsed_ms(callback_start, after_overlay);
      timing.model_input = model_input_ms;
      timing.tf_lookup = elapsed_ms(before_tf, after_tf);
      timing.project = elapsed_ms(after_tf, after_project);
      timing.yolo = elapsed_ms(after_project, after_yolo);
      timing.draw = elapsed_ms(after_yolo, after_draw);
      timing.image_publish = elapsed_ms(after_draw, after_image_publish);
      timing.jpeg_publish = jpeg_publish_ms;
      publish_status(
        current_time, msg,
        static_cast<int>(std::count_if(projected_points.begin(), projected_points.end(), [](const auto & p) {
          return p.has_value();
        })),
        drawn_segments, static_cast<int>(yolo_boxes.size()), "", camera_translation,
        drawn.cols, drawn.rows, timing);
    }
  }

  std::optional<OverlayImage> make_overlay_image(const sensor_msgs::msg::Image::ConstSharedPtr & msg)
  {
    const int width = static_cast<int>(msg->width);
    const int height = static_cast<int>(msg->height);
    const int step = static_cast<int>(msg->step);
    if (width <= 0 || height <= 0 || step <= 0 || msg->data.empty()) {
      return std::nullopt;
    }

    const auto target = target_size(width, height);
    const double scale_x = static_cast<double>(target.width) / static_cast<double>(width);
    const double scale_y = static_cast<double>(target.height) / static_cast<double>(height);
    const auto & encoding = msg->encoding;

    auto rgb = image_to_rgb(*msg, target);
    if (!rgb) {
      return std::nullopt;
    }

    return OverlayImage{*rgb, msg, scale_x, scale_y, encoding};
  }

  double publish_model_input_image(const sensor_msgs::msg::Image::ConstSharedPtr & msg)
  {
    const auto start = std::chrono::steady_clock::now();
    if (!model_input_pub_) {
      return 0.0;
    }
    auto rgb = image_to_rgb(*msg, cv::Size(model_input_width_px_, model_input_height_px_));
    if (!rgb) {
      return elapsed_ms(start, std::chrono::steady_clock::now());
    }
    auto output = make_rgb_image_msg(*rgb, msg->header);
    model_input_pub_->publish(std::move(output));
    return elapsed_ms(start, std::chrono::steady_clock::now());
  }

  std::optional<cv::Mat> image_to_rgb(const sensor_msgs::msg::Image & msg, const cv::Size & target)
  {
    const int width = static_cast<int>(msg.width);
    const int height = static_cast<int>(msg.height);
    const int step = static_cast<int>(msg.step);
    if (width <= 0 || height <= 0 || step <= 0 || msg.data.empty() || target.width <= 0 || target.height <= 0) {
      return std::nullopt;
    }

    const auto & encoding = msg.encoding;
    try {
      if (encoding == sensor_msgs::image_encodings::YUV422 || encoding == "uyvy") {
        return yuv422_to_rgb_scaled(msg.data.data(), width, height, step, target, true);
      }
      if (encoding == sensor_msgs::image_encodings::YUV422_YUY2 ||
        encoding == "yuyv" || encoding == "yuy2")
      {
        return yuv422_to_rgb_scaled(msg.data.data(), width, height, step, target, false);
      }
      if (encoding == sensor_msgs::image_encodings::RGB8 || encoding == "8UC3") {
        cv::Mat image(height, width, CV_8UC3, const_cast<unsigned char *>(msg.data.data()), step);
        return resize_if_needed(image, target, cv::INTER_AREA);
      }
      if (encoding == sensor_msgs::image_encodings::BGR8) {
        cv::Mat image(height, width, CV_8UC3, const_cast<unsigned char *>(msg.data.data()), step);
        cv::Mat resized = resize_if_needed(image, target, cv::INTER_AREA);
        cv::Mat rgb;
        cv::cvtColor(resized, rgb, cv::COLOR_BGR2RGB);
        return rgb;
      }
      if (encoding == sensor_msgs::image_encodings::RGBA8) {
        cv::Mat image(height, width, CV_8UC4, const_cast<unsigned char *>(msg.data.data()), step);
        cv::Mat resized = resize_if_needed(image, target, cv::INTER_AREA);
        cv::Mat rgb;
        cv::cvtColor(resized, rgb, cv::COLOR_RGBA2RGB);
        return rgb;
      }
      if (encoding == sensor_msgs::image_encodings::BGRA8) {
        cv::Mat image(height, width, CV_8UC4, const_cast<unsigned char *>(msg.data.data()), step);
        cv::Mat resized = resize_if_needed(image, target, cv::INTER_AREA);
        cv::Mat rgb;
        cv::cvtColor(resized, rgb, cv::COLOR_BGRA2RGB);
        return rgb;
      }
      if (encoding == sensor_msgs::image_encodings::MONO8 || encoding == "8UC1") {
        cv::Mat image(height, width, CV_8UC1, const_cast<unsigned char *>(msg.data.data()), step);
        cv::Mat resized = resize_if_needed(image, target, cv::INTER_AREA);
        cv::Mat rgb;
        cv::cvtColor(resized, rgb, cv::COLOR_GRAY2RGB);
        return rgb;
      }
    } catch (const cv::Exception & exc) {
      RCLCPP_WARN_THROTTLE(get_logger(), *get_clock(), 2000, "Image conversion failed: %s", exc.what());
      return std::nullopt;
    }
    return std::nullopt;
  }

  sensor_msgs::msg::Image::UniquePtr make_rgb_image_msg(
    const cv::Mat & rgb,
    const std_msgs::msg::Header & header) const
  {
    auto output = std::make_unique<sensor_msgs::msg::Image>();
    output->header = header;
    output->height = static_cast<uint32_t>(rgb.rows);
    output->width = static_cast<uint32_t>(rgb.cols);
    output->encoding = sensor_msgs::image_encodings::RGB8;
    output->is_bigendian = 0;
    output->step = static_cast<uint32_t>(rgb.cols * 3);
    output->data.assign(rgb.datastart, rgb.dataend);
    return output;
  }

  double publish_compressed_overlay(
    const cv::Mat & rgb,
    const std_msgs::msg::Header & header)
  {
    const auto start = std::chrono::steady_clock::now();
    if (!compressed_overlay_pub_) {
      return 0.0;
    }
    try {
      cv::Mat bgr;
      cv::cvtColor(rgb, bgr, cv::COLOR_RGB2BGR);
      std::vector<uint8_t> encoded;
      const std::vector<int> params{cv::IMWRITE_JPEG_QUALITY, output_compressed_jpeg_quality_};
      if (!cv::imencode(".jpg", bgr, encoded, params)) {
        return elapsed_ms(start, std::chrono::steady_clock::now());
      }
      auto output = std::make_unique<sensor_msgs::msg::CompressedImage>();
      output->header = header;
      output->format = "jpeg";
      output->data = std::move(encoded);
      compressed_overlay_pub_->publish(std::move(output));
    } catch (const cv::Exception & exc) {
      RCLCPP_WARN_THROTTLE(
        get_logger(), *get_clock(), 2000, "Compressed overlay encode failed: %s", exc.what());
    }
    return elapsed_ms(start, std::chrono::steady_clock::now());
  }

  cv::Mat yuv422_to_rgb_scaled(
    const uint8_t * data,
    int width,
    int height,
    int step,
    const cv::Size & target,
    bool uyvy) const
  {
    cv::Mat rgb(target.height, target.width, CV_8UC3);
    const double inv_scale_x = static_cast<double>(width) / static_cast<double>(target.width);
    const double inv_scale_y = static_cast<double>(height) / static_cast<double>(target.height);

    for (int oy = 0; oy < target.height; ++oy) {
      const int sy = std::min(height - 1, static_cast<int>(static_cast<double>(oy) * inv_scale_y));
      const auto * src_row = data + sy * step;
      auto * dst_row = rgb.ptr<uint8_t>(oy);
      for (int ox = 0; ox < target.width; ++ox) {
        const int sx = std::min(width - 1, static_cast<int>(static_cast<double>(ox) * inv_scale_x));
        const int pair = (sx / 2) * 4;
        int y = 0;
        int u = 0;
        int v = 0;
        if (uyvy) {
          u = static_cast<int>(src_row[pair + 0]);
          y = static_cast<int>(src_row[pair + ((sx & 1) ? 3 : 1)]);
          v = static_cast<int>(src_row[pair + 2]);
        } else {
          y = static_cast<int>(src_row[pair + ((sx & 1) ? 2 : 0)]);
          u = static_cast<int>(src_row[pair + 1]);
          v = static_cast<int>(src_row[pair + 3]);
        }

        const int c = y - 16;
        const int d = u - 128;
        const int e = v - 128;
        const int r = (298 * c + 409 * e + 128) >> 8;
        const int g = (298 * c - 100 * d - 208 * e + 128) >> 8;
        const int b = (298 * c + 516 * d + 128) >> 8;
        dst_row[ox * 3 + 0] = static_cast<uint8_t>(std::clamp(r, 0, 255));
        dst_row[ox * 3 + 1] = static_cast<uint8_t>(std::clamp(g, 0, 255));
        dst_row[ox * 3 + 2] = static_cast<uint8_t>(std::clamp(b, 0, 255));
      }
    }
    return rgb;
  }

  cv::Size target_size(int width, int height) const
  {
    if (output_max_edge_px_ <= 0 || std::max(width, height) <= output_max_edge_px_) {
      return {width, height};
    }
    const double scale = static_cast<double>(output_max_edge_px_) / static_cast<double>(std::max(width, height));
    int target_width = std::max(2, static_cast<int>(std::round(static_cast<double>(width) * scale)));
    int target_height = std::max(1, static_cast<int>(std::round(static_cast<double>(height) * scale)));
    if (target_width % 2 != 0) {
      ++target_width;
    }
    return {target_width, target_height};
  }

  cv::Mat resize_if_needed(const cv::Mat & image, const cv::Size & target, int interpolation) const
  {
    if (image.cols == target.width && image.rows == target.height) {
      return image.clone();
    }
    cv::Mat resized;
    cv::resize(image, resized, target, 0.0, 0.0, interpolation);
    return resized;
  }

  CameraModel camera_model_from_info(
    const sensor_msgs::msg::CameraInfo & camera_info,
    const sensor_msgs::msg::Image & image,
    double scale_x,
    double scale_y) const
  {
    double fx = camera_info.k[0];
    double fy = camera_info.k[4];
    double cx = camera_info.k[2];
    double cy = camera_info.k[5];
    if (fx <= 0.0 || fy <= 0.0) {
      const double focal = static_cast<double>(std::max(image.width, image.height));
      fx = focal;
      fy = focal;
      cx = static_cast<double>(image.width) * 0.5;
      cy = static_cast<double>(image.height) * 0.5;
    }
    return CameraModel{
      fx * scale_x, fy * scale_y, cx * scale_x, cy * scale_y,
      static_cast<int>(std::round(static_cast<double>(image.width) * scale_x)),
      static_cast<int>(std::round(static_cast<double>(image.height) * scale_y))};
  }

  CameraTranslation get_camera_translation(
    const nav_msgs::msg::Path & path,
    const sensor_msgs::msg::Image & image)
  {
    CameraTranslation fallback{camera_x_m_, camera_y_m_, camera_z_m_, "parameter"};
    if (!use_tf_translation_) {
      return fallback;
    }
    const std::string path_frame = path.header.frame_id;
    std::string camera_frame = image.header.frame_id;
    if (camera_frame.empty() && latest_camera_info_) {
      camera_frame = latest_camera_info_->header.frame_id;
    }
    if (path_frame.empty() || camera_frame.empty()) {
      return fallback;
    }

    try {
      const auto transform = tf_buffer_.lookupTransform(path_frame, camera_frame, tf2::TimePointZero, tf2::durationFromSec(0.02));
      const auto & translation = transform.transform.translation;
      return CameraTranslation{translation.x, translation.y, translation.z, "tf"};
    } catch (const tf2::TransformException &) {
      return fallback;
    }
  }

  std::vector<std::optional<ProjectedPathSample>> project_path(
    const nav_msgs::msg::Path & path,
    const CameraModel & camera_model,
    const CameraTranslation & camera_translation) const
  {
    std::vector<std::optional<ProjectedPathSample>> projected;
    projected.reserve(path.poses.size());
    for (const auto & pose_stamped : path.poses) {
      const auto & position = pose_stamped.pose.position;
      const auto center = project_world_point(position.x, position.y, position.z, camera_model, camera_translation);
      if (!center) {
        projected.push_back(std::nullopt);
        continue;
      }

      const double half_width = path_ribbon_width_m_ * 0.5;
      const auto left = project_world_point(
        position.x, position.y + half_width, position.z, camera_model, camera_translation);
      const auto right = project_world_point(
        position.x, position.y - half_width, position.z, camera_model, camera_translation);
      projected.push_back(ProjectedPathSample{
        center->first,
        left ? std::optional<cv::Point>(left->first) : std::nullopt,
        right ? std::optional<cv::Point>(right->first) : std::nullopt,
        center->second});
    }
    return projected;
  }

  std::optional<std::pair<cv::Point, double>> project_world_point(
    double x_m,
    double y_m,
    double z_m,
    const CameraModel & camera_model,
    const CameraTranslation & camera_translation) const
  {
    const double dx = x_m - camera_translation.x;
    const double dy = y_m - camera_translation.y;
    const double dz = z_m - camera_translation.z;
    const double depth = dx;
    if (depth < min_depth_m_ || depth > max_depth_m_) {
      return std::nullopt;
    }

    const double image_x_m = -dy;
    const double image_y_m = -dz;
    const double u = camera_model.fx * image_x_m / depth + camera_model.cx;
    const double v = camera_model.fy * image_y_m / depth + camera_model.cy;
    if (!std::isfinite(u) || !std::isfinite(v)) {
      return std::nullopt;
    }
    if (u < 0.0 || u >= camera_model.width || v < 0.0 || v >= camera_model.height) {
      return std::nullopt;
    }
    return std::make_pair(cv::Point(static_cast<int>(std::round(u)), static_cast<int>(std::round(v))), depth);
  }

  std::vector<cv::Rect> fresh_yolo_boxes(
    const rclcpp::Time & current_time,
    const sensor_msgs::msg::Image & image,
    double scale_x,
    double scale_y) const
  {
    std::vector<cv::Rect> boxes;
    if (!draw_yolo_boxes_ || !latest_yolo_detections_ ||
      !is_fresh(latest_yolo_received_at_, current_time, stale_yolo_timeout_sec_))
    {
      return boxes;
    }

    const int out_width = static_cast<int>(std::round(static_cast<double>(image.width) * scale_x));
    const int out_height = static_cast<int>(std::round(static_cast<double>(image.height) * scale_y));
    for (const auto & detection : latest_yolo_detections_->detections) {
      if (detection.score < yolo_min_score_) {
        continue;
      }
      const auto & center = detection.bbox.center.position;
      const auto & size = detection.bbox.size;
      if (size.x <= 0.0 || size.y <= 0.0) {
        continue;
      }

      const int left = static_cast<int>(std::round((center.x - size.x * 0.5) * scale_x));
      const int top = static_cast<int>(std::round((center.y - size.y * 0.5) * scale_y));
      const int right = static_cast<int>(std::round((center.x + size.x * 0.5) * scale_x));
      const int bottom = static_cast<int>(std::round((center.y + size.y * 0.5) * scale_y));
      if (right < 0 || bottom < 0 || left >= out_width || top >= out_height) {
        continue;
      }
      const int clipped_left = std::clamp(left, 0, out_width - 1);
      const int clipped_top = std::clamp(top, 0, out_height - 1);
      const int clipped_right = std::clamp(right, 0, out_width - 1);
      const int clipped_bottom = std::clamp(bottom, 0, out_height - 1);
      boxes.emplace_back(
        clipped_left, clipped_top,
        std::max(1, clipped_right - clipped_left),
        std::max(1, clipped_bottom - clipped_top));
    }
    return boxes;
  }

  void draw_path(cv::Mat & image, const std::vector<std::optional<ProjectedPathSample>> & projected_points) const
  {
    std::optional<ProjectedPathSample> previous;
    for (const auto & sample : projected_points) {
      if (!sample) {
        previous.reset();
        continue;
      }
      if (previous) {
        draw_path_segment(image, *previous, *sample);
      }
      previous = sample;
    }

    if (draw_waypoints_) {
      for (const auto & sample : projected_points) {
        if (sample) {
          cv::circle(image, sample->center, point_radius_px_, path_edge_color_rgb_, cv::FILLED, cv::LINE_AA);
        }
      }
    }
  }

  void draw_path_segment(cv::Mat & image, const ProjectedPathSample & start, const ProjectedPathSample & end) const
  {
    if (!start.left || !start.right || !end.left || !end.right) {
      cv::line(image, start.center, end.center, line_color_rgb_, line_width_px_, cv::LINE_AA);
      return;
    }

    const double avg_depth = (start.depth_m + end.depth_m) * 0.5;
    const double depth_ratio = std::clamp(avg_depth / std::max(max_depth_m_, 0.1), 0.0, 1.0);
    const double alpha = path_ribbon_alpha_near_ +
      (path_ribbon_alpha_far_ - path_ribbon_alpha_near_) * depth_ratio;

    std::vector<cv::Point> points{*start.left, *end.left, *end.right, *start.right};
    const auto image_rect = cv::Rect(0, 0, image.cols, image.rows);
    cv::Rect bounds = cv::boundingRect(points) & image_rect;
    if (bounds.area() > 0) {
      cv::Mat roi = image(bounds);
      cv::Mat overlay = roi.clone();
      std::vector<cv::Point> local_points;
      local_points.reserve(points.size());
      for (const auto & point : points) {
        local_points.emplace_back(point.x - bounds.x, point.y - bounds.y);
      }
      cv::fillConvexPoly(overlay, local_points, path_ribbon_color_rgb_, cv::LINE_AA);
      cv::addWeighted(overlay, alpha, roi, 1.0 - alpha, 0.0, roi);
    }

    if (path_edge_width_px_ > 0) {
      cv::line(image, *start.left, *end.left, path_edge_color_rgb_, path_edge_width_px_, cv::LINE_AA);
      cv::line(image, *start.right, *end.right, path_edge_color_rgb_, path_edge_width_px_, cv::LINE_AA);
    }
  }

  void draw_boxes(cv::Mat & image, const std::vector<cv::Rect> & boxes) const
  {
    for (const auto & box : boxes) {
      cv::rectangle(image, box, yolo_box_color_rgb_, yolo_box_width_px_, cv::LINE_AA);
    }
  }

  int count_drawn_segments(const std::vector<std::optional<ProjectedPathSample>> & projected_points) const
  {
    bool has_previous = false;
    int count = 0;
    for (const auto & sample : projected_points) {
      if (!sample) {
        has_previous = false;
        continue;
      }
      if (has_previous) {
        ++count;
      }
      has_previous = true;
    }
    return count;
  }

  bool is_fresh(
    const std::optional<rclcpp::Time> & received_at,
    const rclcpp::Time & current_time,
    double timeout_sec) const
  {
    if (!received_at) {
      return false;
    }
    const double age_sec = (current_time - *received_at).seconds();
    return age_sec >= 0.0 && age_sec <= timeout_sec;
  }

  static double elapsed_ms(
    const std::chrono::steady_clock::time_point & start,
    const std::chrono::steady_clock::time_point & end)
  {
    return std::chrono::duration<double, std::milli>(end - start).count();
  }

  void publish_status(
    const rclcpp::Time & current_time,
    const sensor_msgs::msg::Image::ConstSharedPtr & image,
    int projected_count,
    int drawn_segments,
    int yolo_box_count,
    const std::string & skipped_reason,
    const std::optional<CameraTranslation> & camera_translation,
    int overlay_width,
    int overlay_height,
    const OverlayTimingMs & timing)
  {
    std_msgs::msg::String status;
    std::ostringstream payload;
    payload << "{";
    payload << "\"stamp\":" << current_time.seconds();
    payload << ",\"image_stamp\":" << stamp_to_sec(image->header.stamp);
    payload << ",\"image_age_sec\":" << (current_time.seconds() - stamp_to_sec(image->header.stamp));
    payload << ",\"image_frame_id\":\"" << json_escape(image->header.frame_id) << "\"";
    payload << ",\"image_encoding\":\"" << json_escape(image->encoding) << "\"";
    payload << ",\"image_width\":" << image->width;
    payload << ",\"image_height\":" << image->height;
    payload << ",\"overlay_width\":" << overlay_width;
    payload << ",\"overlay_height\":" << overlay_height;
    payload << ",\"projected_count\":" << projected_count;
    payload << ",\"drawn_segments\":" << drawn_segments;
    payload << ",\"yolo_box_count\":" << yolo_box_count;
    payload << ",\"skipped_reason\":\"" << json_escape(skipped_reason) << "\"";
    payload << ",\"timing_ms\":{";
    payload << "\"total\":" << timing.total;
    payload << ",\"overlay_convert\":" << timing.overlay_convert;
    payload << ",\"model_input\":" << timing.model_input;
    payload << ",\"tf_lookup\":" << timing.tf_lookup;
    payload << ",\"project\":" << timing.project;
    payload << ",\"yolo\":" << timing.yolo;
    payload << ",\"draw\":" << timing.draw;
    payload << ",\"image_publish\":" << timing.image_publish;
    payload << ",\"jpeg_publish\":" << timing.jpeg_publish;
    payload << "}";
    if (camera_translation) {
      payload << ",\"camera_translation\":{";
      payload << "\"source\":\"" << json_escape(camera_translation->source) << "\"";
      payload << ",\"x\":" << camera_translation->x;
      payload << ",\"y\":" << camera_translation->y;
      payload << ",\"z\":" << camera_translation->z;
      payload << "}";
    }
    payload << "}";
    status.data = payload.str();
    status_pub_->publish(status);
  }

  std::string image_topic_;
  std::vector<std::string> image_fallback_topics_;
  std::vector<std::string> image_topics_;
  std::string camera_info_topic_;
  std::string path_topic_;
  std::string yolo_detections_topic_;
  std::string output_image_topic_;
  std::string output_compressed_image_topic_;
  std::string output_status_topic_;
  std::string model_input_image_topic_;

  bool use_tf_translation_{true};
  double camera_x_m_{1.2};
  double camera_y_m_{0.1};
  double camera_z_m_{1.35};
  double min_depth_m_{0.5};
  double max_depth_m_{80.0};
  double path_ribbon_width_m_{2.8};
  double path_ribbon_alpha_near_{0.62};
  double path_ribbon_alpha_far_{0.22};
  int line_width_px_{5};
  int point_radius_px_{3};
  int path_edge_width_px_{2};
  bool draw_waypoints_{false};
  bool draw_yolo_boxes_{true};
  double yolo_min_score_{0.25};
  int yolo_box_width_px_{3};
  double stale_path_timeout_sec_{1.0};
  double stale_yolo_timeout_sec_{1.0};
  double stale_camera_info_timeout_sec_{2.0};
  int output_max_edge_px_{640};
  int model_input_width_px_{1152};
  int model_input_height_px_{384};
  int output_compressed_jpeg_quality_{80};
  bool publish_status_every_frame_{true};

  cv::Scalar path_ribbon_color_rgb_{0, 210, 120};
  cv::Scalar path_edge_color_rgb_{180, 255, 210};
  cv::Scalar line_color_rgb_{0, 255, 80};
  cv::Scalar yolo_box_color_rgb_{255, 220, 0};

  std::vector<rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr> image_subs_;
  rclcpp::Subscription<sensor_msgs::msg::CameraInfo>::SharedPtr camera_info_sub_;
  rclcpp::Subscription<nav_msgs::msg::Path>::SharedPtr path_sub_;
  rclcpp::Subscription<yolo_msgs::msg::DetectionArray>::SharedPtr yolo_sub_;
  rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr overlay_pub_;
  rclcpp::Publisher<sensor_msgs::msg::CompressedImage>::SharedPtr compressed_overlay_pub_;
  rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr model_input_pub_;
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr status_pub_;

  sensor_msgs::msg::CameraInfo::SharedPtr latest_camera_info_;
  nav_msgs::msg::Path::SharedPtr latest_path_;
  yolo_msgs::msg::DetectionArray::SharedPtr latest_yolo_detections_;
  std::optional<rclcpp::Time> latest_camera_info_received_at_;
  std::optional<rclcpp::Time> latest_path_received_at_;
  std::optional<rclcpp::Time> latest_yolo_received_at_;

  tf2_ros::Buffer tf_buffer_;
  tf2_ros::TransformListener tf_listener_;
};

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<E2EPathOverlayNode>();
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
