"""
A*経路の可視化
"""
try:
    import matplotlib
    matplotlib.use('Agg')  # GUIなしバックエンド
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D
    MATPLOTLIB_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ matplotlib利用不可: {e}")
    print("   テキストベースの可視化を使用してください: python3 visualize_path_simple.py")
    MATPLOTLIB_AVAILABLE = False

import numpy as np
from astar_planner_3d import AStarPlanner3D

def visualize_path():
    """経路の可視化"""
    print("=== A* 3D経路可視化テスト ===")
    
    if not MATPLOTLIB_AVAILABLE:
        print("❌ matplotlibが利用できません")
        print("   簡易版可視化を使用してください: python3 visualize_path_simple.py")
        return False
    
    # プランナー作成
    planner = AStarPlanner3D(
        voxel_size=0.1,
        grid_size=(100, 100, 30),
        min_bound=(-5.0, -5.0, 0.0)
    )
    
    # テストケース
    test_cases = [
        ("直線経路", (0.0, 0.0, 0.5), (3.0, 0.0, 0.5)),
        ("斜め経路", (0.0, 0.0, 0.5), (2.0, 2.0, 1.0)),
        ("3D経路", (-2.0, -2.0, 0.5), (2.0, 2.0, 2.0)),
    ]
    
    # 3D可視化
    fig = plt.figure(figsize=(15, 5))
    
    for i, (name, start, goal) in enumerate(test_cases):
        print(f"  {name}を計画中...")
        
        # 経路計画
        path = planner.plan_path(start, goal)
        
        if path is None:
            print(f"    ❌ {name}の経路が見つかりません")
            continue
        
        stats = planner.get_search_stats()
        print(f"    ✅ {name}: {len(path)}点, {stats['computation_time']:.4f}秒")
        
        # 3Dプロット
        ax = fig.add_subplot(1, 3, i+1, projection='3d')
        
        # 経路をプロット
        path_array = np.array(path)
        ax.plot(path_array[:, 0], path_array[:, 1], path_array[:, 2], 
                'b-', linewidth=2, label='経路')
        
        # 開始点と目標点
        ax.scatter(*start, color='green', s=100, label='開始点')
        ax.scatter(*goal, color='red', s=100, label='目標点')
        
        # 設定
        ax.set_xlabel('X [m]')
        ax.set_ylabel('Y [m]')
        ax.set_zlabel('Z [m]')
        ax.set_title(f'{name}\n{len(path)}点, {stats["computation_time"]:.3f}秒')
        ax.legend()
        
        # 軸の範囲設定
        ax.set_xlim(-3, 3)
        ax.set_ylim(-3, 3)
        ax.set_zlim(0, 3)
    
    plt.tight_layout()
    plt.savefig('astar_path_3d.png', dpi=150, bbox_inches='tight')
    print("  📊 3D可視化画像を保存: astar_path_3d.png")
    
    # 2D可視化（上面図）
    fig2, ax2 = plt.subplots(figsize=(10, 8))
    
    colors = ['blue', 'red', 'green']
    for i, (name, start, goal) in enumerate(test_cases):
        path = planner.plan_path(start, goal)
        if path is None:
            continue
        
        path_array = np.array(path)
        ax2.plot(path_array[:, 0], path_array[:, 1], 
                color=colors[i], linewidth=2, label=f'{name} ({len(path)}点)')
        
        ax2.scatter(*start[:2], color=colors[i], s=100, marker='o')
        ax2.scatter(*goal[:2], color=colors[i], s=100, marker='s')
    
    ax2.set_xlabel('X [m]')
    ax2.set_ylabel('Y [m]')
    ax2.set_title('A* 3D経路計画 - 上面図')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.set_aspect('equal')
    
    plt.tight_layout()
    plt.savefig('astar_path_2d.png', dpi=150, bbox_inches='tight')
    print("  📊 2D可視化画像を保存: astar_path_2d.png")
    
    print("✅ 可視化テスト完了")
    return True

if __name__ == "__main__":
    try:
        result = visualize_path()
        if not result:
            exit(1)
    except Exception as e:
        print(f"❌ 可視化テスト失敗: {e}")
        exit(1)
