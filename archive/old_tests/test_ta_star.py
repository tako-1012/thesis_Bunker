#!/usr/bin/env python3
"""
TA*の単体テストスクリプト
"""

import sys
import numpy as np
sys.path.append('/home/hayashi/thesis_work/ros2/ros2_ws/src/bunker_ros2')

from path_planner_3d.terrain_aware_astar_advanced import TerrainAwareAStar

def main():
    print("=" * 70)
    print("TA* (Terrain-Aware A*) 単体テスト")
    print("=" * 70)
    
    # プランナー初期化
    print("\n1. プランナー初期化中...")
    planner = TerrainAwareAStar(
        voxel_size=0.1,
        grid_size=(200, 200, 50),
        terrain_analysis_radius=5,
        enable_online_learning=True
    )
    print("✓ 初期化完了")
    
    # ダミーボクセルグリッド作成
    print("\n2. ダミー地形データ作成中...")
    voxel_grid = np.zeros((200, 200, 50))
    
    # 地形データ設定
    planner.set_terrain_data(voxel_grid, None)
    print("✓ 地形データ設定完了")
    
    # テスト1: 短距離経路
    print("\n3. テスト1: 短距離経路（5m）")
    print("   スタート: (0, 0, 0) → ゴール: (5, 0, 0)")
    
    start = (0.0, 0.0, 0.0)
    goal = (5.0, 0.0, 0.0)
    
    path = planner.plan_path(start, goal)
    
    if path is not None:
        stats = planner.get_search_stats()
        print(f"   ✓ 成功！")
        print(f"      - 経路長: {len(path)} ウェイポイント")
        print(f"      - 計算時間: {stats['computation_time']:.3f}秒")
        print(f"      - 探索ノード数: {stats['nodes_explored']}")
        print(f"      - 戦略切替回数: {stats['strategy_switches']}")
        print(f"      - 遭遇地形タイプ数: {len(stats['terrain_types_encountered'])}")
    else:
        print("   ✗ 失敗")
        return False
    
    # テスト2: 斜め移動
    print("\n4. テスト2: 斜め移動（約10m）")
    print("   スタート: (0, 0, 0) → ゴール: (7, 7, 0)")
    
    start = (0.0, 0.0, 0.0)
    goal = (7.0, 7.0, 0.0)
    
    path = planner.plan_path(start, goal)
    
    if path is not None:
        stats = planner.get_search_stats()
        print(f"   ✓ 成功！")
        print(f"      - 経路長: {len(path)} ウェイポイント")
        print(f"      - 計算時間: {stats['computation_time']:.3f}秒")
        print(f"      - 探索ノード数: {stats['nodes_explored']}")
        print(f"      - 戦略切替回数: {stats['strategy_switches']}")
        print(f"      - 遭遇地形タイプ数: {len(stats['terrain_types_encountered'])}")
    else:
        print("   ✗ 失敗")
        return False
    
    print("\n" + "=" * 70)
    print("すべてのテストが成功しました！")
    print("=" * 70)
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
