#!/bin/bash

cd ~/thesis_work/ros2/ros2_ws/src/bunker_ros2/simulation_manager

echo "======================================================================"
echo "Phase 3-5 自動連続実行スクリプト"
echo "======================================================================"

# Phase 3
echo ""
echo "Phase 3開始: TA-A*優位性実証"
echo "======================================================================"
python3 run_phase3_tastar_superiority.py 2>&1 | tee phase3_experiment.log

if [ $? -eq 0 ]; then
    echo "✅ Phase 3完了"
else
    echo "❌ Phase 3でエラー発生"
    exit 1
fi

# Phase 4
echo ""
echo "Phase 4開始: スケーラビリティ検証"
echo "======================================================================"
python3 run_phase4_scalability.py 2>&1 | tee phase4_experiment.log

if [ $? -eq 0 ]; then
    echo "✅ Phase 4完了"
else
    echo "❌ Phase 4でエラー発生"
    exit 1
fi

# Phase 5
echo ""
echo "Phase 5開始: 可視化・分析"
echo "======================================================================"
python3 run_phase5_visualization.py 2>&1 | tee phase5_experiment.log

if [ $? -eq 0 ]; then
    echo "✅ Phase 5完了"
else
    echo "❌ Phase 5でエラー発生"
    exit 1
fi

# 最終確認
echo ""
echo "======================================================================"
echo "🎉 全Phase完了！"
echo "======================================================================"
echo ""
echo "生成された成果物:"
ls -lh ../results/
echo ""
ls -lh ../results/figures/
echo ""
ls -lh ../results/tables/

echo ""
echo "✅ 完璧な研究が完成しました！"
echo "次: 論文執筆に進んでください"
echo "======================================================================"



