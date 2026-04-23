cmake_minimum_required(VERSION 3.8)
project(shadow_mode_metrics)

if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(std_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)

add_executable(shadow_mode_metrics_node
  src/shadow_mode_metrics_node.cpp
)

target_compile_features(shadow_mode_metrics_node PUBLIC cxx_std_17)
target_include_directories(shadow_mode_metrics_node PUBLIC include)

ament_target_dependencies(shadow_mode_metrics_node
  rclcpp
  std_msgs
  geometry_msgs
)

install(TARGETS
  shadow_mode_metrics_node
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY launch config
  DESTINATION share/${PROJECT_NAME}
  OPTIONAL
)

install(FILES README.md
  DESTINATION share/${PROJECT_NAME}
  OPTIONAL
)

ament_package()
