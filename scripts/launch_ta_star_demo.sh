#!/bin/bash

################################################################################
# TA* Unity Demo 統合起動スクリプト
# 
# 機能:
# 1. ROS2ワークスペースのセットアップ
# 2. TA*経路計画 + Unity可視化システムの起動
# 3. Unity Editorの自動起動（オプション）
#
# 使用方法:
#   ./launch_ta_star_demo.sh [--no-unity] [--no-rviz]
#
# オプション:
#   --no-unity : Unity Editorを自動起動しない
#   --no-rviz  : RVizを起動しない
################################################################################

set -e  # エラーで停止

echo "========================================="
echo "🚀 TA* Unity Demo 起動スクリプト"
echo "========================================="
echo ""

# スクリプトのディレクトリ
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
WORKSPACE_ROOT="$(dirname "$SCRIPT_DIR")"

# ROS2ワークスペースパス
ROS2_WS="$WORKSPACE_ROOT/ros2/ros2_ws"
BUNKER_ROS2="$WORKSPACE_ROOT/ros2/bunker_ros2"

# Unityプロジェクトパス
UNITY_PROJECT="$WORKSPACE_ROOT/unity/PathPlanningVisualization"

# オプション解析
LAUNCH_UNITY=true
LAUNCH_RVIZ=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --no-unity)
            LAUNCH_UNITY=false
            shift
            ;;
        --no-rviz)
            LAUNCH_RVIZ=false
            shift
            ;;
        --with-rviz)
            LAUNCH_RVIZ=true
            shift
            ;;
        *)
            echo "❌ Unknown option: $1"
            echo "Usage: $0 [--no-unity] [--no-rviz] [--with-rviz]"
            exit 1
            ;;
    esac
done

################################################################################
# 1. ROS2環境セットアップ
################################################################################

echo "📦 [1/4] ROS2環境をセットアップ中..."

# ROS2インストールチェック
if [ -z "$ROS_DISTRO" ]; then
    echo "   ROS2環境が検出されません。セットアップを実行します..."
    if [ -f "/opt/ros/humble/setup.bash" ]; then
        source /opt/ros/humble/setup.bash
        echo "   ✅ ROS2 Humble sourced"
    elif [ -f "/opt/ros/foxy/setup.bash" ]; then
        source /opt/ros/foxy/setup.bash
        echo "   ✅ ROS2 Foxy sourced"
    else
        echo "   ❌ ROS2がインストールされていません"
        exit 1
    fi
fi

# ワークスペースのセットアップ
if [ -d "$ROS2_WS" ]; then
    cd "$ROS2_WS"
    
    # ビルドディレクトリ確認
    if [ ! -d "install" ]; then
        echo "   ワークスペースがビルドされていません。ビルドを実行します..."
        colcon build --symlink-install --packages-select bunker_3d_nav
    fi
    
    # setup.bashをsource
    if [ -f "install/setup.bash" ]; then
        source install/setup.bash
        echo "   ✅ ROS2ワークスペース sourced: $ROS2_WS"
    else
        echo "   ⚠️ install/setup.bash が見つかりません。ビルドを実行してください。"
        exit 1
    fi
elif [ -d "$BUNKER_ROS2" ]; then
    # fallback: bunker_ros2ディレクトリ
    cd "$BUNKER_ROS2"
    if [ -f "install/setup.bash" ]; then
        source install/setup.bash
        echo "   ✅ ROS2ワークスペース sourced: $BUNKER_ROS2"
    else
        echo "   ⚠️ install/setup.bash が見つかりません"
    fi
else
    echo "   ❌ ROS2ワークスペースが見つかりません"
    exit 1
fi

echo ""

################################################################################
# 2. TA* + Unity Visualization Launch
################################################################################

echo "🚀 [2/4] TA*経路計画システムを起動中..."

# launchファイルパス確認
LAUNCH_FILE="$ROS2_WS/src/bunker_ros2/bunker_3d_nav/launch/ta_star_unity_demo.launch.py"

if [ ! -f "$LAUNCH_FILE" ]; then
    echo "   ⚠️ Launch file not found: $LAUNCH_FILE"
    echo "   Fallback: 個別ノード起動を試みます"
    
    # Fallback: 個別にノード起動
    echo "   Starting Unity visualization bridge..."
    ros2 run bunker_3d_nav unity_visualization_node.py &
    UNITY_BRIDGE_PID=$!
    sleep 2
    
    echo "   Starting TA* planner node..."
    ros2 run bunker_3d_nav ta_star_planner_node.py &
    TA_STAR_PID=$!
    sleep 2
    
else
    # Launch fileで起動
    ros2 launch bunker_3d_nav ta_star_unity_demo.launch.py \
        voxel_size:=0.2 \
        grid_size_x:=200 \
        grid_size_y:=200 \
        grid_size_z:=50 \
        planning_interval:=2.0 \
        enable_visualization:=true &
    
    LAUNCH_PID=$!
    echo "   ✅ TA* system launched (PID: $LAUNCH_PID)"
fi

sleep 3
echo ""

################################################################################
# 3. Unity Editor起動（オプション）
################################################################################

if [ "$LAUNCH_UNITY" = true ]; then
    echo "🎮 [3/4] Unity Editorを起動中..."
    
    # Unity Editorパス検索
    UNITY_EDITOR=$(find ~/.local/share/Unity/Hub/Editor -name "Unity" -type f 2>/dev/null | head -n 1)
    
    if [ -z "$UNITY_EDITOR" ]; then
        echo "   ⚠️ Unity Editorが見つかりません"
        echo "   Unity Hubから手動で起動してください: $UNITY_PROJECT"
    elif [ ! -d "$UNITY_PROJECT" ]; then
        echo "   ⚠️ Unityプロジェクトが見つかりません: $UNITY_PROJECT"
    else
        echo "   Unity Editor: $UNITY_EDITOR"
        echo "   Project: $UNITY_PROJECT"
        
        "$UNITY_EDITOR" -projectPath "$UNITY_PROJECT" > /dev/null 2>&1 &
        UNITY_PID=$!
        
        echo "   ✅ Unity Editor起動中 (PID: $UNITY_PID)"
        echo "   📝 Unity起動後の手順:"
        echo "      1. Unityが開くまで待つ（1-2分）"
        echo "      2. Playボタンを押す"
        echo "      3. ROS2からの経路データがUnityに表示されます"
    fi
else
    echo "⏭️  [3/4] Unity起動をスキップ (--no-unity指定)"
fi

echo ""

################################################################################
# 4. 起動完了メッセージ
################################################################################

echo "========================================="
echo "✅ システム起動完了"
echo "========================================="
echo ""
echo "📡 ROS2トピック:"
echo "   • /path_3d           : TA*計画経路"
echo "   • /goal_pose         : 目標位置 (PoseStamped)"
echo "   • /current_pose      : 現在位置 (PoseStamped)"
echo "   • /bunker/voxel_grid : 地形データ (開発中)"
echo ""
echo "🎯 テスト用コマンド:"
echo "   # 目標位置を送信 (例: x=5, y=5, z=1)"
echo "   ros2 topic pub -1 /goal_pose geometry_msgs/PoseStamped '{header: {frame_id: \"map\"}, pose: {position: {x: 5.0, y: 5.0, z: 1.0}}}'"
echo ""
echo "   # 現在位置を送信 (例: x=0, y=0, z=0)"
echo "   ros2 topic pub -1 /current_pose geometry_msgs/PoseStamped '{header: {frame_id: \"map\"}, pose: {position: {x: 0.0, y: 0.0, z: 0.0}}}'"
echo ""
echo "   # 経路を確認"
echo "   ros2 topic echo /path_3d"
echo ""
echo "🛑 終了方法:"
echo "   Ctrl+C でこのスクリプトを終了"
echo ""
echo "========================================="

# Ctrl+Cハンドラ
trap 'echo ""; echo "🛑 Shutting down..."; kill $LAUNCH_PID $UNITY_BRIDGE_PID $TA_STAR_PID $UNITY_PID 2>/dev/null; exit' INT TERM

# スクリプトを待機状態に
wait
