"""
A* 3Dエッジケーステストスクリプト
"""
from astar_planner_3d import AStarPlanner3D

def edge_case_test():
    """エッジケーステスト"""
    print("=== A* 3Dエッジケーステスト ===")
    
    planner = AStarPlanner3D(
        voxel_size=0.1,
        grid_size=(100, 100, 30),
        min_bound=(-5.0, -5.0, 0.0)
    )
    
    test_cases = [
        # 異常入力テスト
        ("同じ開始点と目標点", (0.0, 0.0, 0.5), (0.0, 0.0, 0.5)),
        ("非常に近い点", (0.0, 0.0, 0.5), (0.05, 0.05, 0.5)),
        
        # 境界条件テスト
        ("グリッド境界（最小）", (-5.0, -5.0, 0.5), (-4.0, -4.0, 0.5)),
        ("グリッド境界（最大）", (4.0, 4.0, 0.5), (4.9, 4.9, 0.5)),
        ("Z軸境界（最小）", (0.0, 0.0, 0.05), (1.0, 0.0, 0.05)),
        ("Z軸境界（最大）", (0.0, 0.0, 0.95), (1.0, 0.0, 0.95)),
        
        # 極端な距離テスト
        ("極端に長い距離", (-4.9, -4.9, 0.5), (4.9, 4.9, 0.5)),
        ("極端に短い距離", (0.0, 0.0, 0.5), (0.1, 0.0, 0.5)),
        
        # 3D極端ケース
        ("Z軸のみ移動", (0.0, 0.0, 0.5), (0.0, 0.0, 2.0)),
        ("最大Z軸移動", (0.0, 0.0, 0.05), (0.0, 0.0, 0.95)),
    ]
    
    passed = 0
    failed = 0
    
    for name, start, goal in test_cases:
        print(f"\n{name}テスト:")
        print(f"  開始点: {start}")
        print(f"  目標点: {goal}")
        
        try:
            path = planner.plan_path(start, goal)
            
            if path is not None:
                stats = planner.get_search_stats()
                print(f"  ✅ 成功: {len(path)}点, {stats['nodes_explored']}ノード, {stats['computation_time']:.4f}秒")
                passed += 1
            else:
                print(f"  ⚠️ 経路が見つかりません（予想される場合あり）")
                # 同じ点の場合は失敗として扱わない
                if start == goal:
                    print(f"  ✅ 同じ点のため正常")
                    passed += 1
                else:
                    failed += 1
                    
        except Exception as e:
            print(f"  ❌ エラー: {e}")
            failed += 1
    
    # 無効入力テスト
    print("\n=== 無効入力テスト ===")
    invalid_cases = [
        ("グリッド外開始点", (-10.0, -10.0, 0.5), (0.0, 0.0, 0.5)),
        ("グリッド外目標点", (0.0, 0.0, 0.5), (10.0, 10.0, 0.5)),
        ("Z軸範囲外", (0.0, 0.0, -1.0), (1.0, 0.0, 0.5)),
        ("Z軸範囲外（上）", (0.0, 0.0, 0.5), (1.0, 0.0, 2.0)),
    ]
    
    for name, start, goal in invalid_cases:
        print(f"\n{name}テスト:")
        try:
            path = planner.plan_path(start, goal)
            if path is None:
                print(f"  ✅ 正常に失敗（予想通り）")
                passed += 1
            else:
                print(f"  ⚠️ 予想外に成功")
                failed += 1
        except Exception as e:
            print(f"  ✅ 正常にエラー（予想通り）: {e}")
            passed += 1
    
    # 結果サマリー
    print(f"\n=== エッジケーステスト結果 ===")
    print(f"成功: {passed}")
    print(f"失敗: {failed}")
    print(f"成功率: {passed/(passed+failed)*100:.1f}%")
    
    if failed == 0:
        print("✅ 全てのエッジケーステストが成功しました")
        return True
    else:
        print("⚠️ 一部のエッジケーステストが失敗しました")
        return False

if __name__ == "__main__":
    try:
        edge_case_test()
    except Exception as e:
        print(f"❌ エッジケーステスト失敗: {e}")
        exit(1)
