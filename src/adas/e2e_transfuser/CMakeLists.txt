cmake_minimum_required(VERSION 3.8)
project(e2e_transfuser)

find_package(ament_cmake REQUIRED)

install(DIRECTORY config launch
  DESTINATION share/${PROJECT_NAME}
  OPTIONAL
)

install(DIRECTORY e2e_transfuser
  DESTINATION lib/${PROJECT_NAME}
)

install(PROGRAMS
  scripts/e2e_transfuser_node.py
  scripts/e2e_transfuser_check_lead.py
  scripts/e2e_transfuser_benchmark.py
  scripts/e2e_transfuser_probe_lead.py
  DESTINATION lib/${PROJECT_NAME}
)

install(FILES README.md
  DESTINATION share/${PROJECT_NAME}
  OPTIONAL
)

ament_package()
