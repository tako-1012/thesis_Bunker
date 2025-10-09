#!/bin/bash
"""
実験データ記録用スクリプト
必要なトピックを自動記録
"""

# 設定
BAG_NAME="experiment_$(date +%Y%m%d_%H%M%S)"
OUTPUT_DIR="$HOME/thesis_work/data/experiments"
DURATION=600  # 10分間記録

# 出力ディレクトリ作成
mkdir -p "$OUTPUT_DIR"

# 記録するトピック
TOPICS=(
    "/rtabmap/cloud_map"
    "/robot_pose"
    "/goal_pose"
    "/path_3d"
    "/path_cost"
    "/terrain/voxel_grid"
    "/terrain/terrain_info"
    "/terrain/slope_map"
    "/terrain/visualization"
    "/cmd_vel"
    "/odom"
    "/imu/data"
    "/camera/depth/image_raw"
    "/tf"
    "/tf_static"
)

# トピックの存在確認
echo "Checking available topics..."
AVAILABLE_TOPICS=()
for topic in "${TOPICS[@]}"; do
    if ros2 topic list | grep -q "^$topic$"; then
        AVAILABLE_TOPICS+=("$topic")
        echo "✓ $topic"
    else
        echo "✗ $topic (not available)"
    fi
done

if [ ${#AVAILABLE_TOPICS[@]} -eq 0 ]; then
    echo "Error: No topics available for recording"
    exit 1
fi

# 記録開始
echo "Starting recording..."
echo "Bag name: $BAG_NAME"
echo "Output directory: $OUTPUT_DIR"
echo "Duration: $DURATION seconds"
echo "Topics: ${AVAILABLE_TOPICS[*]}"

# ros2 bag record実行
ros2 bag record \
    --output "$OUTPUT_DIR/$BAG_NAME" \
    --duration "$DURATION" \
    "${AVAILABLE_TOPICS[@]}"

# 記録完了
echo "Recording completed!"
echo "Bag file: $OUTPUT_DIR/$BAG_NAME"

# バッグ情報表示
echo "Bag information:"
ros2 bag info "$OUTPUT_DIR/$BAG_NAME"
