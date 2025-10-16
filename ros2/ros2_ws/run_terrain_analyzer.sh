#!/bin/bash
# run_terrain_analyzer.sh - terrain_analyzer起動スクリプト

echo "🚀 terrain_analyzer起動スクリプト"
echo "=================================="

cd ~/thesis_work/ros2/ros2_ws

# 環境設定
echo "🌍 ROS2環境設定中..."
source /opt/ros/humble/setup.bash
source install/setup.bash

# メッセージ確認
echo "🧪 メッセージインポート確認..."
python3 -c "
try:
    from bunker_3d_nav.msg import TerrainInfo, VoxelGrid3D
    print('✅ メッセージインポート成功')
except ImportError as e:
    print(f'❌ メッセージインポート失敗: {e}')
    print('💡 rebuild_messages.shを実行してください')
    exit(1)
"

if [ $? -ne 0 ]; then
    echo "❌ メッセージインポートに失敗しました"
    echo "🔧 解決方法: ./rebuild_messages.sh"
    exit 1
fi

# ROS2ノード起動
echo "🎯 terrain_analyzer起動中..."
ros2 launch bunker_3d_nav terrain_analyzer.launch.py &
TERRAIN_PID=$!

# 起動待機
echo "⏳ ノード起動待機中..."
sleep 5

# ノード状態確認
if ps -p $TERRAIN_PID > /dev/null; then
    echo "✅ terrain_analyzer起動成功 (PID: $TERRAIN_PID)"
else
    echo "❌ terrain_analyzer起動失敗"
    exit 1
fi

# Rviz起動
echo "👁️ Rviz起動中..."
rviz2 -d src/bunker_ros2/config/terrain_visualization.rviz &
RVIZ_PID=$!

# 起動待機
sleep 3

if ps -p $RVIZ_PID > /dev/null; then
    echo "✅ Rviz起動成功 (PID: $RVIZ_PID)"
else
    echo "⚠️ Rviz起動に問題があります"
fi

echo ""
echo "🎉 terrain_analyzer起動完了！"
echo "📋 利用可能なトピック:"
echo "   - /bunker/pointcloud (入力)"
echo "   - /bunker/terrain_info (出力)"
echo "   - /bunker/voxel_grid (出力)"
echo "   - /terrain/markers (可視化)"
echo "   - /terrain/occupancy (可視化)"
echo "   - /terrain/colored_cloud (可視化)"
echo ""
echo "🛑 停止方法: Ctrl+C または kill $TERRAIN_PID $RVIZ_PID"

# シグナルハンドリング
cleanup() {
    echo ""
    echo "🛑 停止中..."
    kill $TERRAIN_PID $RVIZ_PID 2>/dev/null
    echo "✅ 停止完了"
    exit 0
}

trap cleanup SIGINT SIGTERM

# 待機
wait

