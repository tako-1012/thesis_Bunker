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

# Pythonパッケージのインストール（console_scripts 生成に必要）
ament_python_install_package(${PROJECT_NAME})

# メッセージ/サービスファイル追加
rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/TerrainAnalysis.msg"
  "msg/VoxelGrid.msg"
  "msg/SlopeMap.msg"
  "msg/TerrainInfo.msg"
  "msg/VoxelGrid3D.msg"
  "msg/PathCost.msg"
  "msg/Path3D.msg"
  "srv/AnalyzeTerrain.srv"
  DEPENDENCIES
  std_msgs
  geometry_msgs
  sensor_msgs
)

# Python実行ファイルのインストール
install(PROGRAMS
  ${CMAKE_CURRENT_SOURCE_DIR}/terrain_analyzer/voxel_grid_processor.py
  ${CMAKE_CURRENT_SOURCE_DIR}/terrain_analyzer/slope_calculator.py
  ${CMAKE_CURRENT_SOURCE_DIR}/terrain_analyzer/terrain_analyzer_node.py
  ${CMAKE_CURRENT_SOURCE_DIR}/terrain_analyzer/terrain_visualizer.py
  ${CMAKE_CURRENT_SOURCE_DIR}/unity_bridge/ros_to_unity_converter.py
  ${CMAKE_CURRENT_SOURCE_DIR}/unity_bridge/tcp_server_node.py
  DESTINATION lib/${PROJECT_NAME}
)

# TA*, Unity visualization, scenario manager wrapper scripts
install(PROGRAMS
  ${CMAKE_CURRENT_SOURCE_DIR}/scripts/ta_star_planner_node
  ${CMAKE_CURRENT_SOURCE_DIR}/scripts/unity_visualization_node
  ${CMAKE_CURRENT_SOURCE_DIR}/scripts/scenario_publisher
  DESTINATION lib/${PROJECT_NAME}
)

# Fallback: install entire directories to ensure files are deployed
install(DIRECTORY
  ${CMAKE_CURRENT_SOURCE_DIR}/bunker_3d_nav/ta_star_planner/
  ${CMAKE_CURRENT_SOURCE_DIR}/bunker_3d_nav/unity_visualization/
  ${CMAKE_CURRENT_SOURCE_DIR}/bunker_3d_nav/scenario_management/
  DESTINATION lib/${PROJECT_NAME}
  FILES_MATCHING PATTERN "*.py"
  USE_SOURCE_PERMISSIONS
)

# スクリプトディレクトリのインストール - サブディレクトリのみ（wrapperは後で個別指定）
install(DIRECTORY
  scripts/debug
  scripts/evaluation
  scripts/tuning
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



