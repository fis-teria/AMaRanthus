#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/point_cloud2.hpp>
#include <sensor_msgs/point_cloud2_iterator.hpp>
#include <nav_msgs/msg/occupancy_grid.hpp>
#include <visualization_msgs/msg/marker.hpp>

class ObstacleGridNode : public rclcpp::Node {
public:
  ObstacleGridNode() : Node("obstacle_grid_node") {
    // Parameters (可調整)
    declare_parameter<std::string>("points_topic", "/points");
    declare_parameter<std::string>("output_frame", "base_link");
    declare_parameter<double>("grid_resolution", 0.1);     // [m/セル]
    declare_parameter<int>("grid_width_cells", 200);       // X方向セル数（= 20m）
    declare_parameter<int>("grid_height_cells", 200);      // Y方向セル数（= 20m）
    declare_parameter<double>("origin_x", -10.0);          // 地図原点[m]（ロボット基準で左手座標: x前、y左）
    declare_parameter<double>("origin_y", -10.0);
    declare_parameter<double>("z_min", 0.05);              // 地面ノイズ除去
    declare_parameter<double>("z_max", 2.0);               // 上方クリップ
    declare_parameter<double>("obstacle_min_height", 0.10);// 地面からこれ以上を障害物扱い
    declare_parameter<int>("min_points_per_cell", 1);      // 占有判定の最小ヒット数
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

    // QoS はセンサデータ向け
    auto qos = rclcpp::SensorDataQoS();
    sub_ = create_subscription<sensor_msgs::msg::PointCloud2>(
        points_topic_, qos,
        std::bind(&ObstacleGridNode::cloudCallback, this, std::placeholders::_1));

    grid_pub_ = create_publisher<nav_msgs::msg::OccupancyGrid>("obstacle_grid", 1);
    if (publish_markers_) {
      marker_pub_ = create_publisher<visualization_msgs::msg::Marker>("obstacle_cells", 1);
    }

    // OccupancyGrid 共通メタデータ
    grid_msg_.info.resolution = static_cast<float>(res_);
    grid_msg_.info.width = width_;
    grid_msg_.info.height = height_;
    grid_msg_.info.origin.position.x = origin_x_;
    grid_msg_.info.origin.position.y = origin_y_;
    grid_msg_.info.origin.position.z = 0.0;
    grid_msg_.info.origin.orientation.w = 1.0; // no rotation
    grid_msg_.data.resize(width_ * height_, -1); // 未知:-1, 空き:0, 占有:100
  }

private:
  void cloudCallback(const sensor_msgs::msg::PointCloud2::SharedPtr msg) {
    // バッファをクリア
    std::fill(grid_msg_.data.begin(), grid_msg_.data.end(), 0);
    std::vector<uint16_t> counts(width_ * height_, 0);

    // PointCloud2 を直接走査（x,y,z float32 前提）
    sensor_msgs::PointCloud2ConstIterator<float> iter_x(*msg, "x");
    sensor_msgs::PointCloud2ConstIterator<float> iter_y(*msg, "y");
    sensor_msgs::PointCloud2ConstIterator<float> iter_z(*msg, "z");

    for (; iter_x != iter_x.end(); ++iter_x, ++iter_y, ++iter_z) {
      const float x = *iter_x;
      const float y = *iter_y;
      const float z = *iter_z;

      // z クリップ＆地面除去（平坦路想定）
      if (!std::isfinite(x) || !std::isfinite(y) || !std::isfinite(z)) continue;
      if (z < z_min_ || z > z_max_) continue;
      if (z < obs_min_h_) continue; // 障害物最小高さ

      // グリッド座標へ
      const int ix = static_cast<int>(std::floor((x - origin_x_) / res_));
      const int iy = static_cast<int>(std::floor((y - origin_y_) / res_));
      if (ix < 0 || ix >= width_ || iy < 0 || iy >= height_) continue;

      const size_t idx = static_cast<size_t>(iy) * width_ + static_cast<size_t>(ix);
      if (counts[idx] < UINT16_MAX) counts[idx] += 1; // ヒット数をカウント
    }

    // 占有判定（しきい値以上のセルを 100）
    for (size_t i = 0; i < counts.size(); ++i) {
      grid_msg_.data[i] = (counts[i] >= static_cast<uint16_t>(min_pts_cell_)) ? 100 : 0;
    }

    // ヘッダ
    grid_msg_.header.stamp = msg->header.stamp;
    grid_msg_.header.frame_id = output_frame_;
    grid_pub_->publish(grid_msg_);

    // 可視化（占有セルを CUBE_LIST で表示）
    if (publish_markers_) {
      visualization_msgs::msg::Marker mk;
      mk.header = grid_msg_.header;
      mk.ns = "obstacles";
      mk.id = 0;
      mk.type = visualization_msgs::msg::Marker::CUBE_LIST;
      mk.action = visualization_msgs::msg::Marker::ADD;
      mk.scale.x = res_;
      mk.scale.y = res_;
      mk.scale.z = 0.1; // 薄い板として表示
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
};

int main(int argc, char** argv) {
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<ObstacleGridNode>());
  rclcpp::shutdown();
  return 0;
}
