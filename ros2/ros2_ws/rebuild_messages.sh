#!/bin/bash
# rebuild_messages.sh - カスタムメッセージの再ビルドスクリプト

echo "🔧 カスタムメッセージ再ビルド開始..."

cd ~/thesis_work/ros2/ros2_ws

# クリーンビルド
echo "📦 クリーンビルド実行中..."
rm -rf build/ install/ log/

# メッセージ生成
echo "🏗️ メッセージ生成中..."
colcon build --packages-select bunker_3d_nav --cmake-args -DBUILD_TESTING=OFF

# ビルド結果確認
if [ $? -eq 0 ]; then
    echo "✅ ビルド成功！"
else
    echo "❌ ビルド失敗！"
    exit 1
fi

# 環境設定
echo "🌍 環境設定中..."
source install/setup.bash

# 確認
echo "🧪 メッセージインポートテスト..."
python3 -c "
try:
    from bunker_3d_nav.msg import TerrainInfo, VoxelGrid3D
    print('✅ Messages imported successfully!')
    print(f'   TerrainInfo: {TerrainInfo}')
    print(f'   VoxelGrid3D: {VoxelGrid3D}')
except ImportError as e:
    print(f'❌ Import failed: {e}')
    exit(1)
"

if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 メッセージビルド完了！"
    echo "📋 次のステップ:"
    echo "   1. ros2 launch bunker_3d_nav terrain_analyzer.launch.py"
    echo "   2. rviz2 -d src/bunker_ros2/config/terrain_visualization.rviz"
else
    echo "❌ メッセージインポートテスト失敗！"
    exit 1
fi
