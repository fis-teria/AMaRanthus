cmake_minimum_required(VERSION 3.8)
project(e2e_path_overlay)

find_package(ament_cmake REQUIRED)
find_package(OpenCV REQUIRED COMPONENTS core imgproc)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(tf2 REQUIRED)
find_package(tf2_ros REQUIRED)
find_package(yolo_msgs REQUIRED)

add_executable(e2e_path_overlay_node
  src/e2e_path_overlay_node.cpp
)
target_compile_features(e2e_path_overlay_node PUBLIC cxx_std_17)
ament_target_dependencies(e2e_path_overlay_node
  rclcpp
  sensor_msgs
  std_msgs
  nav_msgs
  tf2
  tf2_ros
  yolo_msgs
)
target_link_libraries(e2e_path_overlay_node
  ${OpenCV_LIBRARIES}
)
target_include_directories(e2e_path_overlay_node PRIVATE
  ${OpenCV_INCLUDE_DIRS}
)

install(TARGETS e2e_path_overlay_node
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY config launch
  DESTINATION share/${PROJECT_NAME}
  OPTIONAL
)

install(PROGRAMS
  scripts/e2e_path_overlay_node.py
  DESTINATION lib/${PROJECT_NAME}
)

install(FILES README.md
  DESTINATION share/${PROJECT_NAME}
  OPTIONAL
)

ament_package()
