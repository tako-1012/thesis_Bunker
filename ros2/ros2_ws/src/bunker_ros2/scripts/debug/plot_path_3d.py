#!/usr/bin/env python3
"""
3D経路可視化ツール
matplotlibで3D経路と傾斜プロファイルを可視化
"""

import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import numpy as np
import argparse
import sys
import os
from typing import List, Tuple, Optional
import json

# Add package path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

try:
    from bunker_3d_nav.path_planner_3d.astar_3d import AStar3D
    from bunker_3d_nav.path_planner_3d.cost_function import CostFunction
except ImportError:
    # Fallback for development
    AStar3D = None
    CostFunction = None


class Path3DVisualizer:
    """3D経路を可視化するクラス"""
    
    def __init__(self, figsize: Tuple[int, int] = (15, 10)):
        self.figsize = figsize
        self.colors = ['blue', 'red', 'green', 'orange', 'purple']
    
    def plot_path_3d(self, paths: List[np.ndarray], labels: List[str] = None,
                    terrain_data: Optional[Dict] = None) -> None:
        """3D経路をプロット"""
        fig = plt.figure(figsize=self.figsize)
        ax = fig.add_subplot(111, projection='3d')
        
        # 経路をプロット
        for i, path in enumerate(paths):
            if len(path) > 0:
                color = self.colors[i % len(self.colors)]
                label = labels[i] if labels else f'Path {i+1}'
                
                ax.plot(path[:, 0], path[:, 1], path[:, 2], 
                       color=color, linewidth=2, label=label, marker='o', markersize=3)
        
        # 地形データがあれば表示
        if terrain_data is not None:
            self.plot_terrain(ax, terrain_data)
        
        # 軸ラベルとタイトル
        ax.set_xlabel('X [m]')
        ax.set_ylabel('Y [m]')
        ax.set_zlabel('Z [m]')
        ax.set_title('3D Path Planning Results')
        
        # 凡例
        ax.legend()
        
        # グリッド
        ax.grid(True)
        
        plt.tight_layout()
        plt.show()
    
    def plot_terrain(self, ax: Axes3D, terrain_data: Dict) -> None:
        """地形データをプロット"""
        voxel_grid = terrain_data.get('voxel_grid', np.array([]))
        
        if len(voxel_grid) == 0:
            return
        
        # 障害物ボクセルを表示
        obstacle_positions = np.where(voxel_grid == 2)
        
        if len(obstacle_positions[0]) > 0:
            ax.scatter(obstacle_positions[0], obstacle_positions[1], obstacle_positions[2],
                      c='red', alpha=0.3, s=1, label='Obstacles')
    
    def plot_slope_profile(self, paths: List[np.ndarray], labels: List[str] = None) -> None:
        """傾斜プロファイルをプロット"""
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=self.figsize)
        
        # 各経路の傾斜プロファイル
        for i, path in enumerate(paths):
            if len(path) < 2:
                continue
                
            color = self.colors[i % len(self.colors)]
            label = labels[i] if labels else f'Path {i+1}'
            
            # 経路長を計算
            distances = self.calculate_path_distances(path)
            
            # 傾斜角度を計算
            slopes = self.calculate_slopes(path)
            
            # プロット
            ax1.plot(distances, slopes, color=color, linewidth=2, label=label)
            ax2.plot(distances, path[:, 2], color=color, linewidth=2, label=label)
        
        # 軸ラベルとタイトル
        ax1.set_xlabel('Distance [m]')
        ax1.set_ylabel('Slope Angle [deg]')
        ax1.set_title('Slope Profile Along Path')
        ax1.grid(True)
        ax1.legend()
        
        ax2.set_xlabel('Distance [m]')
        ax2.set_ylabel('Elevation [m]')
        ax2.set_title('Elevation Profile Along Path')
        ax2.grid(True)
        ax2.legend()
        
        plt.tight_layout()
        plt.show()
    
    def calculate_path_distances(self, path: np.ndarray) -> np.ndarray:
        """経路の累積距離を計算"""
        if len(path) < 2:
            return np.array([0])
        
        distances = np.zeros(len(path))
        for i in range(1, len(path)):
            distances[i] = distances[i-1] + np.linalg.norm(path[i] - path[i-1])
        
        return distances
    
    def calculate_slopes(self, path: np.ndarray) -> np.ndarray:
        """経路の傾斜角度を計算"""
        if len(path) < 2:
            return np.array([0])
        
        slopes = np.zeros(len(path))
        for i in range(1, len(path)):
            dx = path[i, 0] - path[i-1, 0]
            dy = path[i, 1] - path[i-1, 1]
            dz = path[i, 2] - path[i-1, 2]
            
            horizontal_distance = np.sqrt(dx**2 + dy**2)
            if horizontal_distance > 0:
                slope_angle = np.degrees(np.arctan(dz / horizontal_distance))
                slopes[i] = slope_angle
            else:
                slopes[i] = slopes[i-1]
        
        return slopes
    
    def plot_cost_analysis(self, cost_data: List[Dict], labels: List[str] = None) -> None:
        """コスト分析をプロット"""
        fig, axes = plt.subplots(2, 2, figsize=self.figsize)
        
        # コスト成分の比較
        cost_types = ['distance_cost', 'slope_cost', 'obstacle_cost', 'stability_cost']
        cost_labels = ['Distance', 'Slope', 'Obstacle', 'Stability']
        
        for i, (cost_type, cost_label) in enumerate(zip(cost_types, cost_labels)):
            ax = axes[i//2, i%2]
            
            for j, data in enumerate(cost_data):
                if cost_type in data:
                    color = self.colors[j % len(self.colors)]
                    label = labels[j] if labels else f'Path {j+1}'
                    
                    ax.bar(j, data[cost_type], color=color, alpha=0.7, label=label)
            
            ax.set_title(f'{cost_label} Cost Comparison')
            ax.set_ylabel('Cost')
            ax.set_xticks(range(len(cost_data)))
            ax.set_xticklabels([f'Path {i+1}' for i in range(len(cost_data))])
            ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.show()
    
    def save_plots(self, output_dir: str, prefix: str = 'path_analysis') -> None:
        """プロットを保存"""
        os.makedirs(output_dir, exist_ok=True)
        
        # 現在の図を保存
        for i, fig in enumerate(plt.get_fignums()):
            plt.figure(fig)
            filename = f'{prefix}_{i+1}.png'
            filepath = os.path.join(output_dir, filename)
            plt.savefig(filepath, dpi=300, bbox_inches='tight')
            print(f'Saved plot: {filepath}')


def load_path_data(filepath: str) -> List[np.ndarray]:
    """経路データをファイルから読み込み"""
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        paths = []
        for path_data in data['paths']:
            path = np.array(path_data)
            paths.append(path)
        
        return paths
    except Exception as e:
        print(f'Error loading path data: {e}')
        return []


def create_sample_paths() -> Tuple[List[np.ndarray], List[str]]:
    """サンプル経路データを作成"""
    # 経路1: 直線経路
    path1 = np.array([
        [0, 0, 0],
        [1, 0, 0.1],
        [2, 0, 0.2],
        [3, 0, 0.3],
        [4, 0, 0.4],
        [5, 0, 0.5]
    ])
    
    # 経路2: 曲線経路
    t = np.linspace(0, 2*np.pi, 20)
    path2 = np.column_stack([
        2.5 + 2.5 * np.cos(t),
        2.5 * np.sin(t),
        0.5 * np.sin(2*t)
    ])
    
    # 経路3: 傾斜経路
    path3 = np.array([
        [0, 0, 0],
        [1, 1, 0.5],
        [2, 2, 1.0],
        [3, 3, 1.5],
        [4, 4, 2.0],
        [5, 5, 2.5]
    ])
    
    paths = [path1, path2, path3]
    labels = ['Straight Path', 'Curved Path', 'Sloped Path']
    
    return paths, labels


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description='3D Path Visualizer')
    parser.add_argument('--input', type=str, help='Input path data file (JSON)')
    parser.add_argument('--output', type=str, help='Output directory for plots')
    parser.add_argument('--sample', action='store_true', help='Use sample data')
    
    args = parser.parse_args()
    
    # 可視化器を作成
    visualizer = Path3DVisualizer()
    
    # データを読み込み
    if args.sample:
        paths, labels = create_sample_paths()
    elif args.input:
        paths = load_path_data(args.input)
        labels = [f'Path {i+1}' for i in range(len(paths))]
    else:
        print('No input data specified. Use --sample or --input')
        return
    
    if len(paths) == 0:
        print('No paths to visualize')
        return
    
    # 可視化実行
    print(f'Visualizing {len(paths)} paths...')
    
    # 3D経路プロット
    visualizer.plot_path_3d(paths, labels)
    
    # 傾斜プロファイル
    visualizer.plot_slope_profile(paths, labels)
    
    # 出力ディレクトリが指定されていれば保存
    if args.output:
        visualizer.save_plots(args.output)


if __name__ == '__main__':
    main()
