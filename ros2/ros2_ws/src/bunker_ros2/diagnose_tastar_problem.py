"""
TA-A*問題診断

実装の問題を特定する
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

def diagnose_problem():
    """TA-A*の問題を診断"""
    print("="*70)
    print("🔍 TA-A*問題診断")
    print("="*70)
    
    # 1. ファイル存在チェック
    print("\n【診断1: ファイル存在チェック】")
    
    files_to_check = [
        'path_planner_3d/terrain_aware_astar_planner_3d.py',
        'path_planner_3d/astar_planner.py',
        'path_planner_3d/config.py'
    ]
    
    for file_path in files_to_check:
        path = Path(file_path)
        if path.exists():
            print(f"  ✅ {file_path}")
        else:
            print(f"  ❌ {file_path} - 存在しない")
    
    # 2. インポートチェック
    print("\n【診断2: インポートチェック】")
    
    try:
        from path_planner_3d.config import PlannerConfig
        print("  ✅ PlannerConfig インポート成功")
        
        config = PlannerConfig.medium_scale()
        print(f"  ✅ Config生成成功")
        print(f"     voxel_size: {config.voxel_size}")
        print(f"     search_limit: {config.max_search_distance}")
    except Exception as e:
        print(f"  ❌ Config エラー: {e}")
    
    try:
        from path_planner_3d.astar_planner import AStarPlanner3D
        print("  ✅ AStarPlanner3D インポート成功")
    except Exception as e:
        print(f"  ❌ AStarPlanner3D エラー: {e}")
    
    try:
        from path_planner_3d.terrain_aware_astar_planner_3d import TerrainAwareAStarPlanner3D
        print("  ✅ TerrainAwareAStarPlanner3D インポート成功")
    except Exception as e:
        print(f"  ❌ TerrainAwareAStarPlanner3D エラー: {e}")
        print("\n  → これが主要な問題の可能性")
    
    # 3. 簡単なテスト
    print("\n【診断3: 簡単な動作テスト】")
    
    try:
        from path_planner_3d.config import PlannerConfig
        from path_planner_3d.astar_planner import AStarPlanner3D
        
        config = PlannerConfig.medium_scale()
        planner = AStarPlanner3D(config)
        
        result = planner.plan_path(
            start=[0, 0, 0.2],
            goal=[5, 5, 0.2],
            timeout=10
        )
        
        if result.success:
            print(f"  ✅ A*テスト成功")
            print(f"     時間: {result.computation_time:.2f}s")
        else:
            print(f"  ⚠️ A*テスト失敗: {result.error_message}")
    
    except Exception as e:
        print(f"  ❌ A*テストエラー: {e}")
    
    try:
        from path_planner_3d.terrain_aware_astar_planner_3d import TerrainAwareAStarPlanner3D
        
        config = PlannerConfig.medium_scale()
        planner = TerrainAwareAStarPlanner3D(config)
        
        result = planner.plan_path(
            start=[0, 0, 0.2],
            goal=[5, 5, 0.2],
            timeout=10
        )
        
        if result.success:
            print(f"  ✅ TA-A*テスト成功")
            print(f"     時間: {result.computation_time:.2f}s")
        else:
            print(f"  ⚠️ TA-A*テスト失敗: {result.error_message}")
    
    except Exception as e:
        print(f"  ❌ TA-A*テストエラー: {e}")
    
    # 4. 診断結果
    print("\n" + "="*70)
    print("診断結果")
    print("="*70)
    
    print("""
可能性のある問題:

1. TA-A*の実装が存在しない
   → path_planner_3d/terrain_aware_astar_planner.py を確認

2. TA-A*の実装にバグがある
   → ゴール判定が厳しすぎる
   → タイムアウトが短すぎる
   → 無限ループに陥っている

3. Phase 2実験でTA-A*が正しく使われていない
   → 古いバージョンが使われている
   → パラメータが適切でない

推奨アクション:
1. TA-A*の実装を確認
2. 簡単なシナリオでデバッグ
3. パラメータをチューニング
4. Phase 2を再実験
""")
    
    print("\n" + "="*70)

if __name__ == '__main__':
    diagnose_problem()
