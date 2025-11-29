#!/bin/bash

echo "======================================================================"
echo "世界最高峰研究の完成"
echo "======================================================================"

cd ~/thesis_work/ros2/ros2_ws/src/bunker_ros2

# Phase Q1-Q5: 基礎強化
echo -e "\n【Phase Q1-Q5: 基礎強化】"
python3 run_research_enhancement.py

# Phase Q6: TA-A* Fast テスト
echo -e "\n【Phase Q6: TA-A* Fast テスト】"
python3 << 'PYEOF'
from path_planner_3d.terrain_aware_astar_fast import TerrainAwareAStarFast
from path_planner_3d.config import PlannerConfig

config = PlannerConfig.medium_scale()
planner = TerrainAwareAStarFast(config)

result = planner.plan_path([0, 0, 0.2], [20, 20, 0.2], timeout=60)
print(f"TA-A* Fast: {'成功' if result.success else '失敗'}")
print(f"時間: {result.computation_time:.2f}s")
PYEOF

# Phase Q7: 機械学習
echo -e "\n【Phase Q7: 機械学習】"
python3 path_planner_3d/ml_path_predictor.py

# Phase Q9: ベンチマーク作成
echo -e "\n【Phase Q9: ベンチマーク作成】"
python3 benchmarks/create_benchmark_dataset.py

# Phase Q10: 新規性分析
echo -e "\n【Phase Q10: 新規性分析】"
python3 analysis/novelty_analysis.py

# Phase Q11: 理論的証明
echo -e "\n【Phase Q11: 理論的証明】"
python3 analysis/theoretical_proof.py

# Phase Q12: アブレーションスタディ
echo -e "\n【Phase Q12: アブレーションスタディ】"
python3 experiments/ablation_study.py

# Phase Q13: エラー分析
echo -e "\n【Phase Q13: エラー分析】"
python3 analysis/error_analysis.py

echo -e "\n======================================================================"
echo "🎉 世界最高峰研究完成！"
echo "======================================================================"

ls -lh ../results/
ls -lh ../docs/



