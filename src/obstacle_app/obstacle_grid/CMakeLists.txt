cmake_minimum_required(VERSION 3.8)
project(obstacle_grid)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
add_compile_options(-O3)

# Keep Jetson/Orin-specific tuning only on aarch64 so x86_64 dev containers can build.
if(CMAKE_SYSTEM_PROCESSOR MATCHES "^(aarch64|ARM64|arm64)")
  add_compile_options(-march=armv8-a+crypto -mtune=cortex-a78)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(visualization_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)

add_executable(obstacle_grid_node src/obstacle_grid_node.cpp)
ament_target_dependencies(obstacle_grid_node
  rclcpp sensor_msgs nav_msgs visualization_msgs geometry_msgs)

install(TARGETS obstacle_grid_node
  DESTINATION lib/${PROJECT_NAME})

install(DIRECTORY config launch
  DESTINATION share/${PROJECT_NAME} OPTIONAL)
ament_package()
