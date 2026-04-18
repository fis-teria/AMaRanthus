cmake_minimum_required(VERSION 3.8)
project(adas_bringup)

find_package(ament_cmake REQUIRED)

install(DIRECTORY launch config src scripts
  DESTINATION share/${PROJECT_NAME} OPTIONAL)

ament_package()
