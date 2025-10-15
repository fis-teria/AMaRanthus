#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/point_cloud2.hpp>
#include <sensor_msgs/point_cloud2_iterator.hpp>
#include <nav_msgs/msg/occupancy_grid.hpp>
#include <visualization_msgs/msg/marker.hpp>

#include <cuda_runtime.h>
#include <vector>
#include <algorithm>
#include <string>
#include <memory>

extern "C" cudaError_t launch_count_hits(
    const float* xs, const float* ys, const float* zs, int n_points,
    float origin_x, float origin_y, float res, int width, int height,
    float z_min, float z_max, float obs_min_h,
    unsigned int* counts, cudaStream_t stream);

#define CUDA_CHECK(ans) { gpuAssert((ans), __FILE__, __LINE__); }
inline void gpuAssert(cudaError_t code, const char *file, int line) {
  if (code != cudaSuccess) {
    fprintf(stderr, "CUDA Error: %s %s %d\n", cudaGetErrorString(code), file, line);
  }
}

class ObstacleGridCudaNode : public rclcpp::Node {
public:
  ObstacleGridCudaNode() : Node("obstacle_grid_cuda_node") {
    // Parameters
    declare_parameter<std::string>("points_topic", "/points");
    declare_parameter<std::string>("output_frame", "base_link");
    declare_parameter<double>("grid_resolution", 0.1);
    declare_parameter<int>("grid_width_cells", 200);
    declare_parameter<int>("grid_height_cells", 200);
    declare_parameter<double>("origin_x", -10.0);
    declare_parameter<double>("origin_y", -10.0);
    declare_parameter<double>("z_min", 0.05);
    declare_parameter<double>("z_max", 2.0);
    declare_parameter<double>("obstacle_min_height", 0.10);
    declare_parameter<int>("min_points_per_cell", 1);
    declare_parameter<bool>("publish_markers", true);

    // Get params
    points_topic_      = get_parameter("points_topic").as_string();
    output_frame_      = get_parameter("output_frame").as_string();
    res_               = get_parameter("grid_resolution").as_double();
    width_             = get_parameter("grid_width_cells").as_int();
    height_            = get_parameter("grid_height_cells").as_int();
    origin_x_          = get_parameter("origin_x").as_double();
    origin_y_          = get_parameter("origin_y").as_double();
    z_min_             = get_parameter("z_min").as_double();
    z_max_             = get_parameter("z_max").as_double();
    obs_min_h_         = get_parameter("obstacle_min_height").as_double();
    min_pts_cell_      = get_parameter("min_points_per_cell").as_int();
    publish_markers_   = get_parameter("publish_markers").as_bool();

    // ROS I/O
    auto qos = rclcpp::SensorDataQoS();
    sub_ = create_subscription<sensor_msgs::msg::PointCloud2>(
        points_topic_, qos,
        std::bind(&ObstacleGridCudaNode::cloudCallback, this, std::placeholders::_1));

    grid_pub_ = create_publisher<nav_msgs::msg::OccupancyGrid>("obstacle_grid", 1);
    if (publish_markers_) {
      marker_pub_ = create_publisher<visualization_msgs::msg::Marker>("obstacle_cells", 1);
    }

    // OccupancyGrid meta
    grid_msg_.info.resolution = static_cast<float>(res_);
    grid_msg_.info.width = width_;
    grid_msg_.info.height = height_;
    grid_msg_.info.origin.position.x = origin_x_;
    grid_msg_.info.origin.position.y = origin_y_;
    grid_msg_.info.origin.position.z = 0.0;
    grid_msg_.info.origin.orientation.w = 1.0;
    grid_msg_.data.resize(width_ * height_, -1);

    // CUDA: 1つのストリームと device バッファを準備（再利用）
    CUDA_CHECK(cudaStreamCreate(&stream_));
    size_t counts_bytes = sizeof(unsigned int) * width_ * height_;
    CUDA_CHECK(cudaMalloc(&d_counts_, counts_bytes));
  }

  ~ObstacleGridCudaNode() override {
    if (d_counts_) cudaFree(d_counts_);
    if (stream_) cudaStreamDestroy(stream_);
    if (d_x_) cudaFree(d_x_);
    if (d_y_) cudaFree(d_y_);
    if (d_z_) cudaFree(d_z_);
    if (h_x_pinned_) cudaFreeHost(h_x_pinned_);
    if (h_y_pinned_) cudaFreeHost(h_y_pinned_);
    if (h_z_pinned_) cudaFreeHost(h_z_pinned_);
  }

private:
  void ensureCapacity(size_t n) {
    // ピン留めホスト＆デバイス領域を必要に応じて拡張（再利用でオーバーヘッド削減）
    if (n > cap_) {
      // free old
      if (d_x_) { cudaFree(d_x_); d_x_ = nullptr; }
      if (d_y_) { cudaFree(d_y_); d_y_ = nullptr; }
      if (d_z_) { cudaFree(d_z_); d_z_ = nullptr; }
      if (h_x_pinned_) { cudaFreeHost(h_x_pinned_); h_x_pinned_ = nullptr; }
      if (h_y_pinned_) { cudaFreeHost(h_y_pinned_); h_y_pinned_ = nullptr; }
      if (h_z_pinned_) { cudaFreeHost(h_z_pinned_); h_z_pinned_ = nullptr; }

      size_t bytes = n * sizeof(float);
      CUDA_CHECK(cudaMalloc(&d_x_, bytes));
      CUDA_CHECK(cudaMalloc(&d_y_, bytes));
      CUDA_CHECK(cudaMalloc(&d_z_, bytes));
      CUDA_CHECK(cudaHostAlloc(&h_x_pinned_, bytes, cudaHostAllocDefault));
      CUDA_CHECK(cudaHostAlloc(&h_y_pinned_, bytes, cudaHostAllocDefault));
      CUDA_CHECK(cudaHostAlloc(&h_z_pinned_, bytes, cudaHostAllocDefault));
      cap_ = n;
    }
  }

  void cloudCallback(const sensor_msgs::msg::PointCloud2::SharedPtr msg) {
    // PointCloud2 をホスト pinned メモリに詰める（x,y,z の float32 前提）
    size_t n_est = static_cast<size_t>(msg->width) * static_cast<size_t>(msg->height);
    if (n_est == 0) return;
    ensureCapacity(n_est);

    size_t n = 0;
    {
      sensor_msgs::PointCloud2ConstIterator<float> it_x(*msg, "x");
      sensor_msgs::PointCloud2ConstIterator<float> it_y(*msg, "y");
      sensor_msgs::PointCloud2ConstIterator<float> it_z(*msg, "z");
      for (; it_x != it_x.end(); ++it_x, ++it_y, ++it_z) {
        h_x_pinned_[n] = *it_x;
        h_y_pinned_[n] = *it_y;
        h_z_pinned_[n] = *it_z;
        ++n;
      }
    }

    // counts を 0 クリア（デバイス側）
    size_t counts_bytes = sizeof(unsigned int) * width_ * height_;
    CUDA_CHECK(cudaMemsetAsync(d_counts_, 0, counts_bytes, stream_));

    // H->D 転送（非同期）
    size_t bytes = n * sizeof(float);
    CUDA_CHECK(cudaMemcpyAsync(d_x_, h_x_pinned_, bytes, cudaMemcpyHostToDevice, stream_));
    CUDA_CHECK(cudaMemcpyAsync(d_y_, h_y_pinned_, bytes, cudaMemcpyHostToDevice, stream_));
    CUDA_CHECK(cudaMemcpyAsync(d_z_, h_z_pinned_, bytes, cudaMemcpyHostToDevice, stream_));

    // カーネル起動
    CUDA_CHECK(launch_count_hits(
      d_x_, d_y_, d_z_, static_cast<int>(n),
      static_cast<float>(origin_x_), static_cast<float>(origin_y_),
      static_cast<float>(res_), width_, height_,
      static_cast<float>(z_min_), static_cast<float>(z_max_),
      static_cast<float>(obs_min_h_),
      d_counts_, stream_));

    // D->H（counts）受け取り
    if (h_counts_.size() != static_cast<size_t>(width_ * height_)) {
      h_counts_.assign(width_ * height_, 0u);
    }
    CUDA_CHECK(cudaMemcpyAsync(h_counts_.data(), d_counts_, counts_bytes,
                               cudaMemcpyDeviceToHost, stream_));
    CUDA_CHECK(cudaStreamSynchronize(stream_));

    // しきい値で OccupancyGrid に反映（CPU）
    grid_msg_.data.assign(width_ * height_, 0);
    for (size_t i = 0; i < h_counts_.size(); ++i) {
      grid_msg_.data[i] = (h_counts_[i] >= static_cast<unsigned int>(min_pts_cell_)) ? 100 : 0;
    }

    // ヘッダ
    grid_msg_.header.stamp = msg->header.stamp;
    grid_msg_.header.frame_id = output_frame_;
    grid_pub_->publish(grid_msg_);

    if (publish_markers_) {
      publishMarkers();
    }
  }

  void publishMarkers() {
    visualization_msgs::msg::Marker mk;
    mk.header = grid_msg_.header;
    mk.ns = "obstacles";
    mk.id = 0;
    mk.type = visualization_msgs::msg::Marker::CUBE_LIST;
    mk.action = visualization_msgs::msg::Marker::ADD;
    mk.scale.x = res_;
    mk.scale.y = res_;
    mk.scale.z = 0.1;
    mk.color.a = 0.8f;
    mk.color.r = 1.0f;
    mk.color.g = 0.2f;
    mk.color.b = 0.2f;

    mk.points.reserve(1024);
    for (int iy = 0; iy < height_; ++iy) {
      for (int ix = 0; ix < width_; ++ix) {
        size_t idx = static_cast<size_t>(iy) * width_ + static_cast<size_t>(ix);
        if (grid_msg_.data[idx] == 100) {
          geometry_msgs::msg::Point p;
          p.x = origin_x_ + (ix + 0.5) * res_;
          p.y = origin_y_ + (iy + 0.5) * res_;
          p.z = 0.0;
          mk.points.push_back(p);
        }
      }
    }
    marker_pub_->publish(mk);
  }

  // Params
  std::string points_topic_, output_frame_;
  double res_, origin_x_, origin_y_, z_min_, z_max_, obs_min_h_;
  int width_, height_, min_pts_cell_;
  bool publish_markers_;

  // ROS
  rclcpp::Subscription<sensor_msgs::msg::PointCloud2>::SharedPtr sub_;
  rclcpp::Publisher<nav_msgs::msg::OccupancyGrid>::SharedPtr grid_pub_;
  rclcpp::Publisher<visualization_msgs::msg::Marker>::SharedPtr marker_pub_;
  nav_msgs::msg::OccupancyGrid grid_msg_;

  // CUDA resources
  cudaStream_t stream_{};
  unsigned int* d_counts_{nullptr};

  float *d_x_{nullptr}, *d_y_{nullptr}, *d_z_{nullptr};
  float *h_x_pinned_{nullptr}, *h_y_pinned_{nullptr}, *h_z_pinned_{nullptr};
  size_t cap_{0};
  std::vector<unsigned int> h_counts_;
};

int main(int argc, char** argv) {
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<ObstacleGridCudaNode>());
  rclcpp::shutdown();
  return 0;
}
