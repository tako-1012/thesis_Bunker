cmake_minimum_required(VERSION 3.8)
project(bunker_3d_nav)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(rclpy REQUIRED)
find_package(std_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(visualization_msgs REQUIRED)
find_package(tf2_ros REQUIRED)
find_package(tf2_geometry_msgs REQUIRED)

# Generate custom messages
rosidl_generate_interfaces(${PROJECT_NAME}
  "bunker_3d_nav/msg/Path3D.msg"
  DEPENDENCIES std_msgs geometry_msgs
)

# Install Python executables
install(PROGRAMS
  bunker_3d_nav/terrain_analyzer/voxel_grid_processor.py
  bunker_3d_nav/terrain_analyzer/slope_calculator.py
  bunker_3d_nav/terrain_analyzer/terrain_analyzer_node.py
  bunker_3d_nav/terrain_analyzer/terrain_visualizer.py
  bunker_3d_nav/unity_bridge/ros_to_unity_converter.py
  bunker_3d_nav/unity_bridge/tcp_server_node.py
  DESTINATION lib/${PROJECT_NAME}
)

# Install configuration files
install(DIRECTORY
  bunker_3d_nav/config/
  DESTINATION share/${PROJECT_NAME}/config
)

# Install launch files
install(DIRECTORY
  bunker_3d_nav/launch/
  DESTINATION share/${PROJECT_NAME}/launch
)

# Export dependencies for Python bindings
ament_export_dependencies(rosidl_default_runtime)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()