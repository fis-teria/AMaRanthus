cmake_minimum_required(VERSION 3.8)
project(shadow_mode_replay_tools)

find_package(ament_cmake REQUIRED)

install(PROGRAMS
  scripts/shadow_mode_replay.py
  DESTINATION lib/${PROJECT_NAME}
)

install(FILES README.md
  DESTINATION share/${PROJECT_NAME}
  OPTIONAL
)

ament_package()
