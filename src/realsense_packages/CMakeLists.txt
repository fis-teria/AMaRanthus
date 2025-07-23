cmake_minimum_required(VERSION 3.8)
project(realsense_packages)
if(NOT CMAKE_C_STANDARD)
  set(CMAKE_C_STANDARD 99)
endif()
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 14)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(message_filters REQUIRED)
find_package(cv_bridge REQUIRED)
#find_package(librealsense2 REQUIRED)
find_package(realsense2 2.54.2)

# インクルードパスの追加
#add include Path
set(WIN_INCLUDE
    C:/local/include
    C:/Python310/include
)
set(WIN_LIB
    C:/local/lib
    C:/Python310/libs
)

set(LINUX_INCLUDE
	/usr/local/include
	#/home/isight/.pyenv/versions/3.8.19/include/python3.8
)
set(LINUX_LIB
	/usr/local/lib
	#/home/isight/.pyenv/versions/3.8.19/lib
)

#ライブラリの追加
if(WIN32)
  include_directories(${WIN_INCLUDE})
  link_directories(${WIN_LIB})
else()
	include_directories(${LINUX_INCLUDE})
	link_directories(${LINUX_LIB})
endif()

# ビルドに関する設定
#set(EXECUTABLES "realsense-sample;localization")
#set(DEPENDENT_LIBS rclcpp;cv_bridge;sensor_msgs;opencv_core;opencv_highgui;opencv_imgcodecs;opencv_imgproc;opencv_videoio;opencv_objdetect;opencv_calib3d;opencv_features2d;pthread;realsense2;python3.8;zmq)
#foreach(target IN LISTS EXECUTABLES)
#  add_executable(${target} src/${target}.cpp)
#  target_link_libraries(${target} ${DEPENDENT_LIBS})
#  ament_target_dependencies(${target} ${DEPENDENT_LIBS})
#  install(TARGETS ${target} DESTINATION lib/${PROJECT_NAME})
#endforeach()

set(EXECUTABLE "realsense-sample;realsense_laser_scan")
foreach(target IN LISTS EXECUTABLE)
  add_executable(${target} src/${target}.cpp)
  ament_target_dependencies(${target} rclcpp OpenCV cv_bridge sensor_msgs message_filters realsense2)
  install(TARGETS ${target} DESTINATION lib/${PROJECT_NAME})
endforeach()



ament_package()

