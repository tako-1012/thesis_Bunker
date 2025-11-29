"""
簡単な経路計画の例
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'path_planner_3d'))

from astar_planner import AStarPlanner3D
from config import PlannerConfig

def main():
    # 設定
    config = PlannerConfig.small_scale()
    
    # プランナー初期化
    planner = AStarPlanner3D(config)
    
    # スタート・ゴール
    start = [0, 0, 0.2]
    goal = [8, 8, 0.2]
    
    print("経路計画開始...")
    print(f"  スタート: {start}")
    print(f"  ゴール: {goal}")
    
    # 経路計画実行
    result = planner.plan_path(start, goal, timeout=60)
    
    # 結果表示
    if result.success:
        print("✅ 成功！")
        print(f"  経路長: {result.path_length:.2f}m")
        print(f"  計算時間: {result.computation_time:.2f}s")
        print(f"  探索ノード数: {result.nodes_explored}")
    else:
        print("❌ 失敗")
        print(f"  エラー: {result.error_message}")

if __name__ == '__main__':
    main()



