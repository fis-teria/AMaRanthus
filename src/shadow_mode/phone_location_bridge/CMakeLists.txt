cmake_minimum_required(VERSION 3.8)
project(phone_location_bridge)

find_package(ament_cmake REQUIRED)

install(DIRECTORY launch
  DESTINATION share/${PROJECT_NAME}
  OPTIONAL
)

install(PROGRAMS
  scripts/phone_location_bridge_node.py
  scripts/phone_location_adb_reverse.sh
  scripts/phone_location_adb_autoreverse.sh
  scripts/install_phone_adb_autoreverse.sh
  scripts/create_phone_https_cert.sh
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY systemd udev
  DESTINATION share/${PROJECT_NAME}
  OPTIONAL
)

install(FILES README.md
  DESTINATION share/${PROJECT_NAME}
  OPTIONAL
)

ament_package()
