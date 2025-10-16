cmake_minimum_required(VERSION 3.8)
project(bunker_3d_nav)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# 依存パッケージ
find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclpy REQUIRED)
find_package(std_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(visualization_msgs REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(rosidl_default_generators REQUIRED)

# カスタムメッセージ生成
rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/TerrainInfo.msg"
  "msg/VoxelGrid3D.msg"
  "msg/PathCost.msg"
  DEPENDENCIES std_msgs geometry_msgs
)

# Python実行ファイルのインストール
install(PROGRAMS
  terrain_analyzer/voxel_grid_processor.py
  terrain_analyzer/slope_calculator.py
  terrain_analyzer/terrain_analyzer_node.py
  terrain_analyzer/terrain_visualizer.py
  unity_bridge/ros_to_unity_converter.py
  unity_bridge/tcp_server_node.py
  DESTINATION lib/${PROJECT_NAME}
)

# スクリプトディレクトリのインストール
install(DIRECTORY
  scripts/
  DESTINATION lib/${PROJECT_NAME}
  USE_SOURCE_PERMISSIONS
)

# 設定ファイルのインストール
install(DIRECTORY
  config/
  DESTINATION share/${PROJECT_NAME}/config
)

# Launchファイルのインストール
install(DIRECTORY
  launch/
  DESTINATION share/${PROJECT_NAME}/launch
)

# メッセージファイルのインストール
install(DIRECTORY
  msg/
  DESTINATION share/${PROJECT_NAME}/msg
)

# テスト
if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  find_package(ament_cmake_pytest REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

# エクスポート
ament_export_dependencies(rosidl_default_runtime)
ament_package()



