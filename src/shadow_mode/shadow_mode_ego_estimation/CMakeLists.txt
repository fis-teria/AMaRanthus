cmake_minimum_required(VERSION 3.8)
project(shadow_mode_ego_estimation)

if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(visualization_msgs REQUIRED)
find_package(tf2 REQUIRED)
find_package(tf2_geometry_msgs REQUIRED)

add_executable(shadow_ego_estimation_node
  src/shadow_ego_estimation_node.cpp
  src/ego_motion_estimator.cpp
)

target_compile_features(shadow_ego_estimation_node PUBLIC cxx_std_17)
target_include_directories(shadow_ego_estimation_node PUBLIC include)

ament_target_dependencies(shadow_ego_estimation_node
  rclcpp
  nav_msgs
  geometry_msgs
  std_msgs
  visualization_msgs
  tf2
  tf2_geometry_msgs
)

install(TARGETS
  shadow_ego_estimation_node
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY launch config
  DESTINATION share/${PROJECT_NAME}
  OPTIONAL
)

ament_package()
