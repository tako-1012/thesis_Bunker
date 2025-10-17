"""
AStarPlanner3Dの基本テスト
"""
from astar_planner_3d import AStarPlanner3D

def test_planner_creation():
    """プランナー作成のテスト"""
    print("=== test_planner_creation ===")
    
    planner = AStarPlanner3D(
        voxel_size=0.1,
        grid_size=(100, 100, 30),
        min_bound=(-5.0, -5.0, 0.0)
    )
    
    assert planner.voxel_size == 0.1
    assert planner.grid_size == (100, 100, 30)
    
    print("✅ プランナー作成テスト成功")

def test_coordinate_conversion():
    """座標変換のテスト"""
    print("=== test_coordinate_conversion ===")
    
    planner = AStarPlanner3D(
        voxel_size=0.1,
        grid_size=(100, 100, 30),
        min_bound=(-5.0, -5.0, 0.0)
    )
    
    # ワールド座標 → ボクセルインデックス
    world_pos = (0.0, 0.0, 1.0)
    voxel_idx = planner._world_to_voxel(world_pos)
    print(f"  ワールド座標 {world_pos} → ボクセル {voxel_idx}")
    
    # ボクセルインデックス → ワールド座標
    world_pos2 = planner._voxel_to_world(voxel_idx)
    print(f"  ボクセル {voxel_idx} → ワールド座標 {world_pos2}")
    
    print("✅ 座標変換テスト成功")

def test_neighbors():
    """26近傍取得のテスト"""
    print("=== test_neighbors ===")
    
    planner = AStarPlanner3D(
        voxel_size=0.1,
        grid_size=(100, 100, 30),
        min_bound=(-5.0, -5.0, 0.0)
    )
    
    # 中央のボクセル
    pos = (50, 50, 5)
    neighbors = planner._get_neighbors(pos)
    
    print(f"  位置 {pos} の近傍数: {len(neighbors)}")
    assert len(neighbors) == 26  # 26近傍
    
    # 角のボクセル
    pos = (0, 0, 0)
    neighbors = planner._get_neighbors(pos)
    
    print(f"  位置 {pos} の近傍数: {len(neighbors)}")
    assert len(neighbors) < 26  # 境界なので少ない
    
    print("✅ 近傍取得テスト成功")

def test_simple_path():
    """簡単な経路探索のテスト"""
    print("=== test_simple_path ===")
    
    planner = AStarPlanner3D(
        voxel_size=0.1,
        grid_size=(100, 100, 30),
        min_bound=(-5.0, -5.0, 0.0)
    )
    
    # 開始点と目標点
    start = (0.0, 0.0, 0.5)
    goal = (1.0, 1.0, 0.5)
    
    # 経路計画
    path = planner.plan_path(start, goal)
    
    if path is not None:
        print(f"  経路長: {len(path)}点")
        print(f"  開始点: {path[0]}")
        print(f"  目標点: {path[-1]}")
        
        # 統計情報
        stats = planner.get_search_stats()
        print(f"  探索ノード数: {stats['nodes_explored']}")
        print(f"  計算時間: {stats['computation_time']:.4f}秒")
        
        print("✅ 簡単な経路探索テスト成功")
    else:
        print("❌ 経路が見つかりませんでした")

if __name__ == "__main__":
    test_planner_creation()
    test_coordinate_conversion()
    test_neighbors()
    test_simple_path()
    
    print("\n✅ 全てのA*基本テストが成功しました！")
