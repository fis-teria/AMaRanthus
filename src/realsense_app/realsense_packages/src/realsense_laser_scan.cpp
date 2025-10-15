#include "rclcpp/rclcpp.hpp"
#include <sensor_msgs/msg/image.hpp>
#include <sensor_msgs/msg/camera_info.hpp>
#include <sensor_msgs/msg/laser_scan.hpp>
#include <cv_bridge/cv_bridge.h>
#include <message_filters/subscriber.h>
#include <message_filters/sync_policies/approximate_time.h>
#include <message_filters/time_synchronizer.h>
#include <opencv2/opencv.hpp>
#include <opencv2/imgcodecs/imgcodecs.hpp>
#include <opencv2/imgproc/imgproc.hpp>
#include <opencv2/core/core.hpp>
#include <vector>
#include <cmath>
#include <algorithm>
#include "librealsense2/rsutil.h"

#include "common.hpp"

class DepthToLaserNode : public rclcpp::Node
{
public:
  rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr depth_sub_;
  rclcpp::Subscription<sensor_msgs::msg::CameraInfo>::SharedPtr camInfo_sub_;
  rclcpp::Publisher<sensor_msgs::msg::LaserScan>::SharedPtr laser_pub_;
  
  DepthToLaserNode() : Node("depth_to_laser_node")
  {
    camInfo_sub_ = this->create_subscription<sensor_msgs::msg::CameraInfo>("/camera/camera/depth/camera_info", 10, std::bind(&DepthToLaserNode::cameraInfo_callback, this, std::placeholders::_1));
    depth_sub_ = this->create_subscription<sensor_msgs::msg::Image>("/camera/camera/depth/image_rect_raw", 10, std::bind(&DepthToLaserNode::depth_callback, this, std::placeholders::_1));
    laser_pub_ = this->create_publisher<sensor_msgs::msg::LaserScan>("/sonor", 10);
  }

private:
  int num = 0;



  float fx_ = 0, fy_ = 0;
  float cx_ = 0, cy_ = 0;
  bool camera_info_received_;

private:
  void cameraInfo_callback(const sensor_msgs::msg::CameraInfo::SharedPtr msg) {
      fx_ = msg->k[0];
      fy_ = msg->k[4];
      cx_ = msg->k[2];
      cy_ = msg->k[5];
      camera_info_received_ = true;
  }

private:
  void depth_callback(const sensor_msgs::msg::Image::SharedPtr depth_cv_image)
  {
        if (!camera_info_received_) return;

        cv_bridge::CvImagePtr cv_ptr;
        try {
            cv_ptr = cv_bridge::toCvCopy(depth_cv_image, depth_cv_image->encoding);
        } catch (cv_bridge::Exception& e) {
            RCLCPP_ERROR(this->get_logger(), "cv_bridge exception: %s", e.what());
            return;
        }

        const cv::Mat& depth_image = cv_ptr->image;
        int width = depth_image.cols;
        int height = depth_image.rows;

        // LaserScanの設定
        auto scan_msg = std::make_unique<sensor_msgs::msg::LaserScan>();
        scan_msg->header = depth_cv_image->header;
        scan_msg->angle_min = -M_PI / 2.0;
        scan_msg->angle_max = M_PI / 2.0;
        scan_msg->angle_increment = M_PI / 180.0;  // 1 deg
        scan_msg->range_min = 0.1;
        scan_msg->range_max = 5.0;

        int num_ranges = static_cast<int>((scan_msg->angle_max - scan_msg->angle_min) / scan_msg->angle_increment);
        std::vector<std::vector<float>> bins(num_ranges); // 各角度binに複数距離を入れて中央値処理

        for (int v = 0; v < height; v += 5) {
            for (int u = 0; u < width; u += 5) {
                float z = depth_image.at<uint16_t>(v, u) * 0.001f; // mm→m
                if (z <= 0.0f || std::isnan(z)) continue;

                float x = (u - cx_) * z / fx_;
                float y = (v - cy_) * z / fy_;

                // 地面付近だけに限定
                if (y < -0.1f || y > 0.3f) continue;

                float angle = std::atan2(x, z);
                float distance = std::hypot(x, z);

                int index = static_cast<int>((angle - scan_msg->angle_min) / scan_msg->angle_increment);
                if (index >= 0 && index < num_ranges) {
                    bins[index].push_back(distance);
                }
            }
        }

        scan_msg->ranges.resize(num_ranges, std::numeric_limits<float>::infinity());

        for (int i = 0; i < num_ranges; ++i) {
            if (!bins[i].empty()) {
                std::sort(bins[i].begin(), bins[i].end());
                float median = bins[i][bins[i].size() / 2];
                scan_msg->ranges[i] = median;
            }
        }

        laser_pub_->publish(std::move(scan_msg));
    }
};

int main(int argc, char *argv[])
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<DepthToLaserNode>());
  rclcpp::shutdown();
  return 0;
}
