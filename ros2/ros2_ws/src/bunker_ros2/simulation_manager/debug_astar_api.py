#!/usr/bin/env python3
"""
A*のAPI問題をデバッグ
"""
import sys
from pathlib import Path

# パス設定
current_dir = Path(__file__).parent
sys.path.append(str(current_dir))
sys.path.append(str(current_dir.parent / "path_planner_3d"))

def debug_astar():
    print("="*70)
    print("A*のAPI問題デバッグ")
    print("="*70)
    
    # 元のA*をインポート
    try:
        from astar_planner_3d import AStarPlanner3D as OriginalAStar
        print("✅ 元のA*インポート成功")
        original = OriginalAStar()
        print(f"   クラス: {type(original)}")
        print(f"   メソッド: {[m for m in dir(original) if not m.startswith('_')]}")
    except Exception as e:
        print(f"❌ 元のA*インポート失敗: {e}")
        original = None
    
    # 修正版A*をインポート
    try:
        from astar_planner_3d_fixed import AStarPlanner3D as FixedAStar
        print("\n✅ 修正版A*インポート成功")
        fixed = FixedAStar()
        print(f"   クラス: {type(fixed)}")
        print(f"   メソッド: {[m for m in dir(fixed) if not m.startswith('_')]}")
    except Exception as e:
        print(f"\n❌ 修正版A*インポート失敗: {e}")
        fixed = None
    
    # API比較
    if original and fixed:
        print("\n" + "="*70)
        print("APIの比較")
        print("="*70)
        
        # plan_pathメソッドのシグネチャ確認
        import inspect
        
        print("\n元のA* plan_path:")
        try:
            sig = inspect.signature(original.plan_path)
            print(f"  {sig}")
        except Exception as e:
            print(f"  取得失敗: {e}")
        
        print("\n修正版A* plan_path:")
        try:
            sig = inspect.signature(fixed.plan_path)
            print(f"  {sig}")
        except Exception as e:
            print(f"  取得失敗: {e}")
    
    # 実際に呼び出してみる
    print("\n" + "="*70)
    print("実際の呼び出しテスト")
    print("="*70)
    
    # テスト用のシナリオデータ
    test_scenario = {
        'start': [0.0, 0.0, 0.0],
        'goal': [1.0, 1.0, 0.0],
        'terrain': {
            'terrain_type': 'flat_terrain',
            'obstacles': [],
            'slope': {'max_slope': 15.0}
        }
    }
    
    if original:
        print("\n元のA*でテスト:")
        try:
            result = original.plan_path(
                start=test_scenario['start'],
                goal=test_scenario['goal']
            )
            if result is not None:
                print(f"  ✅ 成功: 経路発見")
                print(f"  📊 計算時間: {original.last_search_stats['computation_time']:.2f}s")
                print(f"  📏 経路長: {len(result)}点")
            else:
                print(f"  ❌ 失敗: 経路なし")
        except Exception as e:
            print(f"  ❌ エラー: {e}")
            import traceback
            traceback.print_exc()
    
    if fixed:
        print("\n修正版A*でテスト:")
        try:
            result = fixed.plan_path(
                start=test_scenario['start'],
                goal=test_scenario['goal']
            )
            if result is not None:
                print(f"  ✅ 成功: 経路発見")
                print(f"  📊 計算時間: {fixed.last_search_stats['computation_time']:.2f}s")
                print(f"  📏 経路長: {len(result)}点")
            else:
                print(f"  ❌ 失敗: 経路なし")
        except Exception as e:
            print(f"  ❌ エラー: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    debug_astar()
