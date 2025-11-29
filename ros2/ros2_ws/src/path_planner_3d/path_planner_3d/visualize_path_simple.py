"""
A*経路の簡易可視化（matplotlibなし）
"""
from astar_planner_3d import AStarPlanner3D
import numpy as np

def visualize_path_text(start, goal, path):
    """テキストベースの経路可視化"""
    print("\n" + "="*50)
    print("  経路可視化")
    print("="*50)
    
    if path is None:
        print("❌ 経路が見つかりませんでした")
        return
    
    path_array = np.array(path)
    
    print(f"\n開始点: ({start[0]:.2f}, {start[1]:.2f}, {start[2]:.2f})")
    print(f"目標点: ({goal[0]:.2f}, {goal[1]:.2f}, {goal[2]:.2f})")
    print(f"\n経路長: {len(path)}点")
    
    # 統計情報
    x_range = path_array[:, 0].max() - path_array[:, 0].min()
    y_range = path_array[:, 1].max() - path_array[:, 1].min()
    z_range = path_array[:, 2].max() - path_array[:, 2].min()
    
    print(f"\nX範囲: {x_range:.2f}m")
    print(f"Y範囲: {y_range:.2f}m")
    print(f"Z範囲: {z_range:.2f}m")
    
    # 経路の距離
    total_distance = 0.0
    for i in range(len(path) - 1):
        p1 = np.array(path[i])
        p2 = np.array(path[i+1])
        distance = np.linalg.norm(p2 - p1)
        total_distance += distance
    
    print(f"\n総距離: {total_distance:.2f}m")
    print(f"直線距離: {np.linalg.norm(np.array(goal) - np.array(start)):.2f}m")
    print(f"効率: {(np.linalg.norm(np.array(goal) - np.array(start)) / total_distance * 100):.1f}%")
    
    # 経路の一部を表示（最初と最後の5点）
    print("\n経路の一部:")
    print("  最初の5点:")
    for i in range(min(5, len(path))):
        print(f"    {i+1}. ({path[i][0]:.2f}, {path[i][1]:.2f}, {path[i][2]:.2f})")
    
    if len(path) > 10:
        print("  ...")
        print("  最後の5点:")
        for i in range(max(0, len(path)-5), len(path)):
            print(f"    {i+1}. ({path[i][0]:.2f}, {path[i][1]:.2f}, {path[i][2]:.2f})")
    
    print("\n✅ 経路可視化完了")

if __name__ == "__main__":
    # プランナー作成
    planner = AStarPlanner3D(
        voxel_size=0.1,
        grid_size=(100, 100, 30),
        min_bound=(-5.0, -5.0, 0.0)
    )
    
    # テストケース1: 斜め経路
    print("\n=== テストケース1: 斜め経路 ===")
    start = (0.0, 0.0, 0.5)
    goal = (3.0, 3.0, 1.5)
    path = planner.plan_path(start, goal)
    
    if path:
        stats = planner.get_search_stats()
        print(f"探索ノード数: {stats['nodes_explored']}")
        print(f"計算時間: {stats['computation_time']:.4f}秒")
        visualize_path_text(start, goal, path)
    
    # テストケース2: 長距離
    print("\n=== テストケース2: 長距離経路 ===")
    start = (-4.0, -4.0, 0.5)
    goal = (4.0, 4.0, 1.5)
    path = planner.plan_path(start, goal)
    
    if path:
        stats = planner.get_search_stats()
        print(f"探索ノード数: {stats['nodes_explored']}")
        print(f"計算時間: {stats['computation_time']:.4f}秒")
        visualize_path_text(start, goal, path)
