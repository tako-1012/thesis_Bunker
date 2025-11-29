#!/bin/bash

echo "🚀 大規模シミュレーション実行開始"
echo "======================================"

cd ~/thesis_work/ros2/ros2_ws/src/bunker_ros2/simulation_manager

# Step 1: シナリオ生成（既に完了している場合はスキップ）
if [ ! -d "scenarios" ] || [ -z "$(ls -A scenarios)" ]; then
    echo "📊 Step 1: シナリオ生成"
    python3 scenario_generator.py
else
    echo "✅ Step 1: シナリオ既存（スキップ）"
fi

# Step 2: シミュレーション実行
echo ""
echo "🤖 Step 2: シミュレーション実行"
python3 simulation_runner.py

# Step 3: データ収集
echo ""
echo "📊 Step 3: データ収集"
python3 data_collector.py

# Step 4: 完了
echo ""
echo "======================================"
echo "✅ 大規模シミュレーション完了!"
echo "======================================"



