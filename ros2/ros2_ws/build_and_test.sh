#!/bin/bash
set -e

echo "=== Building bunker_3d_nav package ==="
cd ~/thesis_work/ros2/ros2_ws

# クリーンビルド
rm -rf build/bunker_3d_nav install/bunker_3d_nav

# ビルド実行
colcon build --packages-select bunker_3d_nav --symlink-install

# 環境設定
source install/setup.bash

echo "=== Running unit tests ==="
cd src/bunker_ros2/bunker_3d_nav/terrain_analyzer

# 既存テスト実行
python3 test_voxel_processor.py
python3 test_slope_calculator.py
python3 test_integration.py

echo "=== Running ROS2 node test ==="
cd ../test
python3 test_terrain_analyzer_node.py

echo "=== Build and test completed successfully ==="
