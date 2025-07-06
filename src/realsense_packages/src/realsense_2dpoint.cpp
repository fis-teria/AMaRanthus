#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/image.hpp"
#include <sensor_msgs/msg/imu.hpp>
#include <cv_bridge/cv_bridge.h>
#include <message_filters/subscriber.h>
#include <message_filters/sync_policies/approximate_time.h>
#include <message_filters/time_synchronizer.h>
#include <opencv2/opencv.hpp>
#include <opencv2/imgcodecs/imgcodecs.hpp>
#include <opencv2/imgproc/imgproc.hpp>
#include <opencv2/core/core.hpp>
#include <vector>
#include "librealsense2/rsutil.h"

#include "common.hpp"

class ImageCombiner : public rclcpp::Node
{
private:
  int num = 0;
  std::vector<int> lut;

public:
  message_filters::Subscriber<sensor_msgs::msg::Image> rgb_sub_;
  message_filters::Subscriber<sensor_msgs::msg::Image> depth_sub_;
  message_filters::Subscriber<sensor_msgs::msg::Imu> imu_sub_;
  rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr combined_image_pub_;
  typedef message_filters::sync_policies::ApproximateTime<sensor_msgs::msg::Image, sensor_msgs::msg::Image> approximate_policy;
  message_filters::Synchronizer<approximate_policy> sync_;

  ImageCombiner()
      : Node("realsense_2dpoint_cloud_node"),

        sync_(approximate_policy(10), rgb_sub_, depth_sub_)
  {
    common::make_LUT(lut);
    rgb_sub_.subscribe(this, "/camera/camera/color/image_raw");
    depth_sub_.subscribe(this, "/camera/camera/aligned_depth_to_color/image_raw");
    combined_image_pub_ = this->create_publisher<sensor_msgs::msg::Image>("/sonor_image", 10);

    sync_.registerCallback(&ImageCombiner::topic_callback, this);
  }

public:
  void topic_callback(const sensor_msgs::msg::Image::SharedPtr rgb_image, const sensor_msgs::msg::Image::SharedPtr depth_image)
  {
    // Convert ROS Image messages to OpenCV Mat
    cv::Mat rgb_cv_image = cv_bridge::toCvShare(rgb_image, "bgr8")->image;
    cv::Mat depth_cv_image = cv_bridge::toCvShare(depth_image, "16UC1")->image;
    cv::Mat rgbd_cv_image = cv::Mat(depth_cv_image.rows, depth_cv_image.cols, CV_8UC3);
    cv::Mat elbp_cv_image, dedge_cv_image;

    double minV, maxV;
    cv::Point minP, maxP;
    cv::minMaxLoc(depth_cv_image, &minV, &maxV, &minP, &maxP);
    //std::cout << "minV = " << minV << std::endl;
    //std::cout << "maxV = " << maxV << std::endl;
    //std::cout << depth_cv_image.cols << " " << depth_cv_image.rows << std::endl;
    /*
    max border norm
    3000  3050 
    10000 10050
    18200 18200 140
    */
    
    int border = 10050;
    float norm = 255 / 140;

    for (int x = 0; x < depth_cv_image.cols; x++)
    {
      for (int y = 0; y < depth_cv_image.rows; y++)
      {
        if (depth_cv_image.at<unsigned short>(y, x) > border)//3000 or 10000 or182000
        {
          depth_cv_image.at<unsigned short>(y, x) = border;//3050 or 10050 or 18200
        }
        // std::cout << depth_cv_image << std::endl;
      }
    }
    // Normalize depth image for visualization
    cv::Mat depth_norm_image;
    cv::Mat sonor_img = cv::Mat(depth_cv_image.rows, depth_cv_image.cols, CV_8UC3);
    sonor_img = cv::Scalar::all(0);
    depth_cv_image.copyTo(depth_norm_image);
    cv::normalize(depth_cv_image, depth_cv_image, 0, 140, cv::NORM_MINMAX, CV_8UC1);
    float world_pos[3];
    int y_pos_;
    int x_pos_;

    // std::cout << rgbd_cv_image.size() << " " << depth_cv_image.size() << std::endl;
    for (int x = 0; x < depth_cv_image.cols; x++)
    {
      for (int y = 0; y < depth_cv_image.rows; y++)
      {
        if (depth_cv_image.at<unsigned char>(y, x) > 130 || depth_cv_image.at<unsigned char>(y, x) == 0)
        {
          sonor_img.at<cv::Vec3b>(y, x) = cv::Vec3b(0, 0, 0);
        }
        else
        {
          common::doDeprojectPosition(depth_cv_image, x, y, world_pos);
          y_pos_ = sonor_img.rows - world_pos[2] * (sonor_img.rows / 2) / border;
          x_pos_ = sonor_img.cols / 2 + world_pos[0] * (sonor_img.cols / 2) / 10000;
          //std::cout << x_pos_ << " " << y_pos_ << std::endl;
          sonor_img.at<cv::Vec3b>(y_pos_, x_pos_) = cv::Vec3b(depth_cv_image.at<unsigned char>(y, x), 255, 255); // S = I_ij *255/ (depth_max/130)
        }
      }
    }
    // Convert normalized 8-bit depth image to 3-channel for visualization
    // cv::cvtColor(depth_cv_image, depth_cv_image, cv::COLOR_GRAY2BGR);
    cv::cvtColor(sonor_img, sonor_img, cv::COLOR_HSV2BGR);

    // Combine the images side by side

    cv::resize(sonor_img, sonor_img, cv::Size(848, 480));
 
    cv::Mat view_img;
    cv::resize(sonor_img, view_img, cv::Size(), 0.7, 0.7);

    cv::imshow("combined_cv_image", view_img);
    // Convert combined OpenCV Mat to ROS Image message
    sensor_msgs::msg::Image::SharedPtr sonor_image = cv_bridge::CvImage(rgb_image->header, "bgr8", sonor_img).toImageMsg();
    combined_image_pub_->publish(*sonor_image);
    RCLCPP_INFO(this->get_logger(), "Combined image published");

    cv::waitKey(200);
  }
};

int main(int argc, char *argv[])
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<ImageCombiner>());
  rclcpp::shutdown();
  return 0;
}
