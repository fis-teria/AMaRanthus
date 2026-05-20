cmake_minimum_required(VERSION 3.8)
project(shadow_mode_localization_fusion)

find_package(ament_cmake REQUIRED)

install(DIRECTORY config launch
  DESTINATION share/${PROJECT_NAME}
  OPTIONAL
)

install(DIRECTORY shadow_mode_localization_fusion
  DESTINATION lib/${PROJECT_NAME}
)

install(PROGRAMS
  scripts/shadow_localization_fusion_node.py
  DESTINATION lib/${PROJECT_NAME}
)

install(FILES README.md
  DESTINATION share/${PROJECT_NAME}
  OPTIONAL
)

ament_package()
