"""
A* 3Dパフォーマンステストスクリプト
"""
import time
import numpy as np
from astar_planner_3d import AStarPlanner3D

def performance_test():
    """パフォーマンステスト"""
    print("=== A* 3Dパフォーマンステスト ===")
    
    # テストケース定義（境界から0.1m内側に調整）
    test_cases = [
        ("小規模", (50, 50, 15), (0.0, 0.0, 0.5), (1.0, 1.0, 0.5)),
        ("中規模", (100, 100, 30), (0.0, 0.0, 0.5), (4.9, 4.9, 0.5)),
        ("大規模", (200, 200, 50), (0.0, 0.0, 0.5), (9.9, 9.9, 0.5)),
    ]
    
    results = []
    
    for name, grid_size, start, goal in test_cases:
        print(f"\n{name}テスト実行中...")
        
        # プランナー作成
        planner = AStarPlanner3D(
            voxel_size=0.1,
            grid_size=grid_size,
            min_bound=(-grid_size[0]*0.05, -grid_size[1]*0.05, 0.0)
        )
        
        # 複数回実行して平均を計算
        times = []
        nodes_explored = []
        path_lengths = []
        
        for i in range(5):  # 5回実行
            start_time = time.time()
            path = planner.plan_path(start, goal)
            end_time = time.time()
            
            if path is not None:
                stats = planner.get_search_stats()
                times.append(end_time - start_time)
                nodes_explored.append(stats['nodes_explored'])
                path_lengths.append(len(path))
            else:
                print(f"  ❌ {name}テスト{i+1}回目: 経路が見つかりません")
        
        if times:
            avg_time = np.mean(times)
            avg_nodes = np.mean(nodes_explored)
            avg_length = np.mean(path_lengths)
            
            print(f"  ✅ {name}:")
            print(f"     平均計算時間: {avg_time:.4f}秒")
            print(f"     平均探索ノード数: {avg_nodes:.0f}")
            print(f"     平均経路長: {avg_length:.0f}点")
            
            results.append({
                'name': name,
                'grid_size': grid_size,
                'avg_time': avg_time,
                'avg_nodes': avg_nodes,
                'avg_length': avg_length
            })
        else:
            print(f"  ❌ {name}: 全てのテストで経路が見つかりませんでした")
    
    # スケーラビリティ分析
    print("\n=== スケーラビリティ分析 ===")
    if len(results) >= 2:
        for i in range(1, len(results)):
            prev = results[i-1]
            curr = results[i]
            
            time_ratio = curr['avg_time'] / prev['avg_time']
            node_ratio = curr['avg_nodes'] / prev['avg_nodes']
            
            print(f"{prev['name']} → {curr['name']}:")
            print(f"  計算時間比: {time_ratio:.2f}x")
            print(f"  探索ノード比: {node_ratio:.2f}x")
    
    # メモリ使用量テスト（簡易版）
    print("\n=== メモリ使用量テスト ===")
    import psutil
    import os
    
    process = psutil.Process(os.getpid())
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB
    
    # 大規模テスト実行（境界内に調整）
    planner = AStarPlanner3D(
        voxel_size=0.1,
        grid_size=(200, 200, 50),
        min_bound=(-10.0, -10.0, 0.0)
    )
    
    path = planner.plan_path((0.0, 0.0, 0.5), (9.9, 9.9, 0.5))
    
    final_memory = process.memory_info().rss / 1024 / 1024  # MB
    memory_increase = final_memory - initial_memory
    
    print(f"メモリ増加量: {memory_increase:.1f}MB")
    
    if memory_increase < 500:
        print("✅ メモリ使用量: 良好")
    else:
        print("⚠️ メモリ使用量: 注意が必要")
    
    # 結果サマリー
    print("\n=== パフォーマンスサマリー ===")
    for result in results:
        print(f"{result['name']}: {result['avg_time']:.4f}秒, {result['avg_nodes']:.0f}ノード")
    
    print("✅ パフォーマンステスト完了")
    return True

if __name__ == "__main__":
    try:
        performance_test()
    except Exception as e:
        print(f"❌ パフォーマンステスト失敗: {e}")
        exit(1)
