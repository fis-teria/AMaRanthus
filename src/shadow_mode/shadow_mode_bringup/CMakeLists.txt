cmake_minimum_required(VERSION 3.8)
project(shadow_mode_bringup)

find_package(ament_cmake REQUIRED)

install(DIRECTORY launch config
  DESTINATION share/${PROJECT_NAME}
  OPTIONAL
)

install(FILES README.md
  DESTINATION share/${PROJECT_NAME}
  OPTIONAL
)

ament_package()
