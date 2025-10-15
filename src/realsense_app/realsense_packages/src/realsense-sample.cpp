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
      : Node("image_combiner_node"),

        sync_(approximate_policy(10), rgb_sub_, depth_sub_)
  {
    common::make_LUT(lut);
    rgb_sub_.subscribe(this, "/camera/camera/color/image_raw");
    depth_sub_.subscribe(this, "/camera/camera/aligned_depth_to_color/image_raw");
    imu_sub_.subscribe(this, "/camera/camera/imu");
    combined_image_pub_ = this->create_publisher<sensor_msgs::msg::Image>("/output_image", 10);

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
    
    int border = 18200;
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
    depth_cv_image.copyTo(depth_norm_image);
    cv::normalize(depth_cv_image, depth_cv_image, 0, 130, cv::NORM_MINMAX, CV_8UC1);

    // std::cout << rgbd_cv_image.size() << " " << depth_cv_image.size() << std::endl;
    for (int x = 0; x < depth_cv_image.cols; x++)
    {
      for (int y = 0; y < depth_cv_image.rows; y++)
      {
        if (depth_cv_image.at<unsigned char>(y, x) > 130 || depth_cv_image.at<unsigned char>(y, x) == 0)
        {
          rgbd_cv_image.at<cv::Vec3b>(y, x) = cv::Vec3b(0, 0, 0);
        }
        else
        {
          rgbd_cv_image.at<cv::Vec3b>(y, x) = cv::Vec3b(depth_cv_image.at<unsigned char>(y, x), 255, 255); // S = I_ij *255/ (depth_max/130)
        }
      }
    }
    // Convert normalized 8-bit depth image to 3-channel for visualization
    // cv::cvtColor(depth_cv_image, depth_cv_image, cv::COLOR_GRAY2BGR);
    cv::cvtColor(rgbd_cv_image, rgbd_cv_image, cv::COLOR_HSV2BGR);

    // Combine the images side by side

    cv::resize(rgb_cv_image, rgb_cv_image, cv::Size(848, 480));
    // cv::resize(depth_cv_image, depth_cv_image, cv::Size(848, 480));
    cv::resize(rgbd_cv_image, rgbd_cv_image, cv::Size(848, 480));

    common::cvt_ELBP(rgb_cv_image, elbp_cv_image, this->lut);
    common::cvt_depth_edge_image(elbp_cv_image, rgbd_cv_image, dedge_cv_image);

    /*
    cv::imwrite(common::make_path("data/images/corridor/floor/color", this->num, ".jpg"), rgb_cv_image);
    //cv::imwrite(common::make_path("data/images/amalab/test/depth", this->num, ".jpg"), depth_cv_image);
    cv::imwrite(common::make_path("data/images/corridor/floor/depth", this->num, ".jpg"), rgbd_cv_image);
    cv::imwrite(common::make_path("data/images/corridor/floor/dedge", this->num, ".jpg"), dedge_cv_image);
    this->num++;//*/
    /*const int key = cv::waitKey(100);
    if (key == 'q'/) // qボタンが押されたとき
    {
      cv::imwrite(common::make_path("data/images/corridor/relative_position/color", this->num, ".jpg"), rgb_cv_image);
      cv::imwrite(common::make_path("data/images/corridor/relative_position/depth", this->num, ".jpg"), rgbd_cv_image);
      cv::imwrite(common::make_path("data/images/corridor/relative_position/dedge", this->num, ".jpg"), dedge_cv_image);
      this->num++;
    }//*/
    cv::Mat combined_cv_image;
    // cv::hconcat(rgb_cv_image, depth_cv_image, combined_cv_image);
    cv::hconcat(rgb_cv_image, rgbd_cv_image, combined_cv_image);
    cv::hconcat(combined_cv_image, dedge_cv_image, combined_cv_image);

    cv::Mat view_img;
    cv::resize(combined_cv_image, view_img, cv::Size(), 0.7, 0.7);

    //cv::imshow("combined_cv_image", view_img);
    // Convert combined OpenCV Mat to ROS Image message
    sensor_msgs::msg::Image::SharedPtr combined_image = cv_bridge::CvImage(rgb_image->header, "bgr8", combined_cv_image).toImageMsg();
    combined_image_pub_->publish(*combined_image);
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
