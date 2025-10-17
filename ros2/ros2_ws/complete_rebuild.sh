#!/bin/bash
set -e  # エラーで停止

echo "🔧 完全リビルド開始..."

cd ~/thesis_work/ros2/ros2_ws

# 1. 完全クリーン
echo "1. クリーニング..."
rm -rf build/ install/ log/

# 2. ROS2環境設定
echo "2. ROS2環境設定..."
source /opt/ros/humble/setup.bash

# 3. ビルド
echo "3. ビルド実行..."
colcon build --packages-select bunker_3d_nav --symlink-install

# 4. 環境再設定
echo "4. 環境再設定..."
source install/setup.bash

# 5. Pythonバインディング確認
echo "5. Pythonバインディング確認..."
python3 << 'EOF'
try:
    from bunker_3d_nav.msg import TerrainInfo, VoxelGrid3D
    print("✅ カスタムメッセージ正常にインポート！")
    print(f"  - TerrainInfo: OK")
    print(f"  - VoxelGrid3D: OK")
except Exception as e:
    print(f"❌ インポート失敗: {e}")
    exit(1)
EOF

# 6. テスト実行
echo "6. テスト実行..."
cd src/bunker_ros2/terrain_analyzer
python3 test_voxel_processor.py
python3 test_slope_calculator.py
python3 test_integration.py

cd ../unity_bridge
python3 test_unity_bridge.py

echo "✅ 完全リビルド成功！"




