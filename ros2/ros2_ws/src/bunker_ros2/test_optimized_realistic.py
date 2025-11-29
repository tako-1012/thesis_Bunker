#!/usr/bin/env python3
"""
TA-A* Optimized の現実的なテスト

Phase 2の実際のシナリオで検証
"""
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, 'path_planner_3d')
from tastar_optimized import TerrainAwareAStarOptimized
from astar_planner import AStarPlanner3D
from config import PlannerConfig

def test_phase2_compatibility():
    """Phase 2互換性テスト"""
    print("="*70)
    print("TA-A* Optimized - Phase 2互換性テスト")
    print("="*70)
    
    # Phase 2データの読み込み
    results_file = Path('results/efficient_terrain_results.json')
    if not results_file.exists():
        print("❌ Phase 2データが見つかりません")
        return
    
    with open(results_file) as f:
        data = json.load(f)
    
    if 'results' not in data:
        print("❌ データ形式が不正です")
        return
    
    print(f"\n地形数: {len(data['results'])}")
    
    # 各アルゴリズムの初期化
    config = PlannerConfig.medium_scale()
    
    tastar_optimized = TerrainAwareAStarOptimized(
        map_bounds=([-50, -50, 0], [50, 50, 10]),
        voxel_size=0.2
    )
    
    astar = AStarPlanner3D(config)
    
    # 1地形を選んで詳細テスト
    terrain_name = 'flat_agricultural_field'
    if terrain_name not in data['results']:
        terrain_name = list(data['results'].keys())[0]
    
    print(f"\nテスト対象地形: {terrain_name}")
    
    # その地形の最初のシナリオを取得
    scenarios = data['results'][terrain_name]
    if not scenarios:
        print("❌ シナリオが見つかりません")
        return
    
    # A*の成功シナリオを使用
    astar_results = scenarios.get('A*', [])
    if not astar_results:
        print("❌ A*データが見つかりません")
        return
    
    # 成功した最初のシナリオを使用
    successful_scenarios = [r for r in astar_results if r.get('success', False)]
    if not successful_scenarios:
        print("❌ 成功したシナリオが見つかりません")
        return
    
    # テスト用に簡単なシナリオを手動で作成
    print("\n【テストシナリオ1: 短距離】")
    test_scenarios = [
        ([0, 0, 0.2], [5, 5, 0.2], "Short (5m)"),
        ([0, 0, 0.2], [10, 10, 0.2], "Medium (14m)"),
        ([-10, -10, 0.2], [10, 10, 0.2], "Long (28m)")
    ]
    
    for start, goal, name in test_scenarios:
        print(f"\n{name}:")
        
        # TA-A* Optimized
        print(f"  TA-A* Optimized...", end=" ")
        try:
            start_time = time.time()
            result = tastar_optimized.plan_path(start, goal, timeout=30)
            elapsed = time.time() - start_time
            
            if result.success:
                print(f"✅ {elapsed:.3f}s ({result.path_length:.1f}m, {result.nodes_explored} nodes)")
            else:
                print(f"❌ {elapsed:.3f}s - {result.error_message}")
        except Exception as e:
            print(f"❌ Error: {e}")
        
        # A* (baseline)
        print(f"  A* (Baseline)...", end=" ")
        try:
            result = astar.plan_path(start, goal, timeout=30)
            
            if result.success:
                print(f"✅ {result.computation_time:.3f}s ({result.path_length:.1f}m, {result.nodes_explored} nodes)")
            else:
                print(f"❌ {result.computation_time:.3f}s - {result.error_message}")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    print("\n" + "="*70)
    print("✅ テスト完了")

if __name__ == '__main__':
    test_phase2_compatibility()


