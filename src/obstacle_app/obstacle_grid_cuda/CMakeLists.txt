cmake_minimum_required(VERSION 3.18)  # CUDA 11+ 推奨
project(pcl_obstacle)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Orin Nano 最適化の一例
add_compile_options(-O3 -march=armv8-a+crypto -mtune=cortex-a78)
# CUDA 側の最適化
set(CMAKE_CUDA_STANDARD 14)
set(CMAKE_CUDA_STANDARD_REQUIRED ON)
add_compile_options($<$<COMPILE_LANGUAGE:CUDA>:--use_fast_math -O3>)

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(visualization_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)

enable_language(CUDA)

# CUDA kernels
add_library(obg_kernels STATIC src/kernels.cu)
set_target_properties(obg_kernels PROPERTIES POSITION_INDEPENDENT_CODE ON)

# Node
add_executable(obstacle_grid_cuda src/obstacle_grid_cuda.cpp)
ament_target_dependencies(obstacle_grid_cuda
  rclcpp sensor_msgs nav_msgs visualization_msgs geometry_msgs)
target_link_libraries(obstacle_grid_cuda obg_kernels cuda cudart)

install(TARGETS obstacle_grid_cuda
  DESTINATION lib/${PROJECT_NAME})

ament_package()
