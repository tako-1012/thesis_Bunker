#!/usr/bin/env python3
"""
path_visualizer.py
3D経路可視化システム

機能:
- 3D空間での経路表示
- 地形（障害物・勾配）の可視化
- スタート・ゴールの明示
- 複数シナリオの比較表示
- 高解像度PNG/PDF出力
"""

import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path
from typing import List, Tuple, Optional
import sys

# 3Dプロット用のインポート（互換性対応）
try:
    from mpl_toolkits.mplot3d import Axes3D
    HAS_3D = True
    print("✅ 3Dプロットが利用可能です")
except ImportError:
    print("⚠️ 3Dプロットが利用できません。2Dプロットにフォールバックします。")
    HAS_3D = False

sys.path.insert(0, str(Path(__file__).parent.parent / 'path_planner_3d'))
sys.path.insert(0, str(Path(__file__).parent))

from simulation_runner import SimulationResult, TerrainGenerator
from scenario_generator import ScenarioGenerator, Scenario

class PathVisualizer:
    """経路可視化クラス"""
    
    def __init__(self):
        self.output_dir = Path("results/path_visualizations")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 設定
        self.grid_size = (100, 100, 30)
        self.voxel_size = 0.1
        self.min_bound = (-5.0, -5.0, 0.0)
    
    def load_scenario_and_result(
        self, 
        scenario_id: int,
        scenarios_path: str = "scenarios",
        results_path: str = "results/final_results.json"
    ) -> Tuple[Optional[Scenario], Optional[SimulationResult], Optional[List]]:
        """シナリオと結果を読み込み"""
        
        # シナリオ読み込み
        generator = ScenarioGenerator()
        scenarios = generator.load_scenarios(scenarios_path)
        scenario = next((s for s in scenarios if s.scenario_id == scenario_id), None)
        
        if not scenario:
            print(f"⚠️ シナリオ{scenario_id}が見つかりません")
            return None, None, None
        
        # 結果読み込み
        with open(results_path, 'r') as f:
            results_data = json.load(f)
        
        result = next((r for r in results_data if r['scenario_id'] == scenario_id), None)
        
        if not result:
            print(f"⚠️ 結果{scenario_id}が見つかりません")
            return scenario, None, None
        
        result_obj = SimulationResult(**result)
        
        # 経路を再計算（結果には経路データが含まれていないため）
        path = self._recompute_path(scenario)
        
        return scenario, result_obj, path
    
    def _recompute_path(self, scenario: Scenario) -> Optional[List]:
        """経路を再計算"""
        from astar_planner_3d import AStarPlanner3D
        
        # プランナー初期化
        planner = AStarPlanner3D(
            voxel_size=self.voxel_size,
            grid_size=self.grid_size,
            min_bound=self.min_bound
        )
        
        # 地形生成
        occupancy_grid = TerrainGenerator.generate_occupancy_grid(
            scenario, self.grid_size, self.voxel_size, self.min_bound
        )
        slope_grid = TerrainGenerator.generate_slope_grid(
            scenario, self.grid_size, self.voxel_size, self.min_bound
        )
        
        # 地形データを設定
        planner.set_terrain_data(occupancy_grid, slope_grid)
        
        # スタート・ゴール（ワールド座標）
        start_world = scenario.start_position
        goal_world = scenario.goal_position
        
        # 経路計画
        path = planner.plan_path(start_world, goal_world)
        
        if path:
            # ワールド座標をグリッド座標に変換
            path_grid = [self._world_to_grid(p) for p in path]
            return path_grid
        
        return None
    
    def _world_to_grid(self, world_pos: Tuple[float, float, float]) -> Tuple[int, int, int]:
        """ワールド座標→グリッド座標"""
        x = int((world_pos[0] - self.min_bound[0]) / self.voxel_size)
        y = int((world_pos[1] - self.min_bound[1]) / self.voxel_size)
        z = int((world_pos[2] - self.min_bound[2]) / self.voxel_size)
        
        x = max(0, min(x, self.grid_size[0] - 1))
        y = max(0, min(y, self.grid_size[1] - 1))
        z = max(0, min(z, self.grid_size[2] - 1))
        
        return (x, y, z)
    
    def _grid_to_world(self, grid_pos: Tuple[int, int, int]) -> Tuple[float, float, float]:
        """グリッド座標→ワールド座標"""
        x = grid_pos[0] * self.voxel_size + self.min_bound[0]
        y = grid_pos[1] * self.voxel_size + self.min_bound[1]
        z = grid_pos[2] * self.voxel_size + self.min_bound[2]
        return (x, y, z)
    
    def visualize_single_path(
        self,
        scenario_id: int,
        show_obstacles: bool = True,
        show_terrain: bool = False
    ):
        """単一経路の可視化（3Dまたは2D）"""
        
        print(f"\n🎨 シナリオ{scenario_id}を可視化中...")
        
        scenario, result, path = self.load_scenario_and_result(scenario_id)
        
        if not scenario or not path:
            print("⚠️ 可視化データが不足しています")
            return
        
        if HAS_3D:
            self._visualize_single_path_3d(scenario, result, path, show_obstacles)
        else:
            self._visualize_single_path_2d(scenario, result, path, show_obstacles)
    
    def _visualize_single_path_3d(
        self,
        scenario: Scenario,
        result: Optional[SimulationResult],
        path: List,
        show_obstacles: bool
    ):
        """3D経路可視化"""
        
        # 地形データ生成
        occupancy_grid = TerrainGenerator.generate_occupancy_grid(
            scenario, self.grid_size, self.voxel_size, self.min_bound
        )
        
        # 3Dプロット作成
        fig = plt.figure(figsize=(12, 10))
        ax = fig.add_subplot(111, projection='3d')
        
        # 経路をワールド座標に変換
        path_world = [self._grid_to_world(p) for p in path]
        path_x, path_y, path_z = zip(*path_world)
        
        # 経路プロット
        ax.plot(path_x, path_y, path_z, 
                'b-', linewidth=3, label='Optimal Path', alpha=0.8)
        
        # スタート地点
        start_world = scenario.start_position
        ax.scatter(*start_world, c='green', s=200, marker='o', 
                  edgecolors='black', linewidths=2, label='Start', zorder=10)
        
        # ゴール地点
        goal_world = scenario.goal_position
        ax.scatter(*goal_world, c='red', s=200, marker='*', 
                  edgecolors='black', linewidths=2, label='Goal', zorder=10)
        
        # 障害物表示
        if show_obstacles:
            obstacle_coords = np.where(occupancy_grid == 1)
            if len(obstacle_coords[0]) > 0:
                # サンプリング（全部表示すると重いので）
                sample_size = min(5000, len(obstacle_coords[0]))
                indices = np.random.choice(len(obstacle_coords[0]), sample_size, replace=False)
                
                obs_x = [obstacle_coords[0][i] * self.voxel_size + self.min_bound[0] for i in indices]
                obs_y = [obstacle_coords[1][i] * self.voxel_size + self.min_bound[1] for i in indices]
                obs_z = [obstacle_coords[2][i] * self.voxel_size + self.min_bound[2] for i in indices]
                
                ax.scatter(obs_x, obs_y, obs_z, c='gray', s=1, alpha=0.3, label='Obstacles')
        
        # ラベル・タイトル
        ax.set_xlabel('X (m)', fontsize=12)
        ax.set_ylabel('Y (m)', fontsize=12)
        ax.set_zlabel('Z (m)', fontsize=12)
        
        title = f"Scenario {scenario.scenario_id}: {scenario.terrain_params.terrain_type}\n"
        if result:
            title += f"Success: {result.path_found}, Time: {result.computation_time:.2f}s, Length: {result.path_length:.2f}m"
        
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.legend(loc='upper right', fontsize=10)
        
        # 視点調整
        ax.view_init(elev=25, azim=45)
        
        # グリッド
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # 保存
        output_file = self.output_dir / f"path_scenario_{scenario.scenario_id:03d}_3d.png"
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"✅ 3D可視化保存: {output_file}")
    
    def _visualize_single_path_2d(
        self,
        scenario: Scenario,
        result: Optional[SimulationResult],
        path: List,
        show_obstacles: bool
    ):
        """2D経路可視化（フォールバック）"""
        
        # 地形データ生成
        occupancy_grid = TerrainGenerator.generate_occupancy_grid(
            scenario, self.grid_size, self.voxel_size, self.min_bound
        )
        
        # 2Dプロット作成
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        
        # 経路をワールド座標に変換
        path_world = [self._grid_to_world(p) for p in path]
        path_x, path_y, path_z = zip(*path_world)
        
        # XY平面での経路
        ax1.plot(path_x, path_y, 'b-', linewidth=3, label='Optimal Path', alpha=0.8)
        ax1.scatter(scenario.start_position[0], scenario.start_position[1], 
                   c='green', s=200, marker='o', edgecolors='black', linewidths=2, label='Start')
        ax1.scatter(scenario.goal_position[0], scenario.goal_position[1], 
                   c='red', s=200, marker='*', edgecolors='black', linewidths=2, label='Goal')
        
        # 障害物表示（XY平面）
        if show_obstacles:
            obstacle_coords = np.where(occupancy_grid == 1)
            if len(obstacle_coords[0]) > 0:
                sample_size = min(2000, len(obstacle_coords[0]))
                indices = np.random.choice(len(obstacle_coords[0]), sample_size, replace=False)
                
                obs_x = [obstacle_coords[0][i] * self.voxel_size + self.min_bound[0] for i in indices]
                obs_y = [obstacle_coords[1][i] * self.voxel_size + self.min_bound[1] for i in indices]
                
                ax1.scatter(obs_x, obs_y, c='gray', s=1, alpha=0.3, label='Obstacles')
        
        ax1.set_xlabel('X (m)', fontsize=12)
        ax1.set_ylabel('Y (m)', fontsize=12)
        ax1.set_title('Path (XY Plane)', fontsize=14, fontweight='bold')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # XZ平面での経路（高さ情報）
        ax2.plot(path_x, path_z, 'b-', linewidth=3, label='Optimal Path', alpha=0.8)
        ax2.scatter(scenario.start_position[0], scenario.start_position[2], 
                   c='green', s=200, marker='o', edgecolors='black', linewidths=2, label='Start')
        ax2.scatter(scenario.goal_position[0], scenario.goal_position[2], 
                   c='red', s=200, marker='*', edgecolors='black', linewidths=2, label='Goal')
        
        ax2.set_xlabel('X (m)', fontsize=12)
        ax2.set_ylabel('Z (m)', fontsize=12)
        ax2.set_title('Path (XZ Plane)', fontsize=14, fontweight='bold')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # 全体タイトル
        title = f"Scenario {scenario.scenario_id}: {scenario.terrain_params.terrain_type}"
        if result:
            title += f"\nSuccess: {result.path_found}, Time: {result.computation_time:.2f}s, Length: {result.path_length:.2f}m"
        
        fig.suptitle(title, fontsize=16, fontweight='bold')
        plt.tight_layout()
        
        # 保存
        output_file = self.output_dir / f"path_scenario_{scenario.scenario_id:03d}_2d.png"
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"✅ 2D可視化保存: {output_file}")
    
    def visualize_multiple_paths(
        self,
        scenario_ids: List[int],
        grid_layout: Tuple[int, int] = (2, 3)
    ):
        """複数経路の比較可視化"""
        
        print(f"\n🎨 {len(scenario_ids)}個のシナリオを比較可視化中...")
        
        if HAS_3D:
            self._visualize_multiple_paths_3d(scenario_ids, grid_layout)
        else:
            self._visualize_multiple_paths_2d(scenario_ids, grid_layout)
    
    def _visualize_multiple_paths_3d(
        self,
        scenario_ids: List[int],
        grid_layout: Tuple[int, int]
    ):
        """3D複数経路比較"""
        
        rows, cols = grid_layout
        fig = plt.figure(figsize=(6*cols, 5*rows))
        
        for idx, scenario_id in enumerate(scenario_ids[:rows*cols], 1):
            scenario, result, path = self.load_scenario_and_result(scenario_id)
            
            if not scenario or not path:
                continue
            
            ax = fig.add_subplot(rows, cols, idx, projection='3d')
            
            # 経路プロット
            path_world = [self._grid_to_world(p) for p in path]
            path_x, path_y, path_z = zip(*path_world)
            ax.plot(path_x, path_y, path_z, 'b-', linewidth=2, alpha=0.8)
            
            # スタート・ゴール
            ax.scatter(*scenario.start_position, c='green', s=100, marker='o')
            ax.scatter(*scenario.goal_position, c='red', s=100, marker='*')
            
            # タイトル
            title = f"#{scenario_id}: {scenario.terrain_params.terrain_type}"
            if result:
                title += f"\n{result.computation_time:.1f}s, {result.path_length:.1f}m"
            ax.set_title(title, fontsize=10)
            
            ax.set_xlabel('X (m)')
            ax.set_ylabel('Y (m)')
            ax.set_zlabel('Z (m)')
            ax.view_init(elev=20, azim=45)
        
        plt.tight_layout()
        
        # 保存
        output_file = self.output_dir / "path_comparison_multiple_3d.png"
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"✅ 3D比較図保存: {output_file}")
    
    def _visualize_multiple_paths_2d(
        self,
        scenario_ids: List[int],
        grid_layout: Tuple[int, int]
    ):
        """2D複数経路比較"""
        
        rows, cols = grid_layout
        fig = plt.figure(figsize=(8*cols, 4*rows))
        
        for idx, scenario_id in enumerate(scenario_ids[:rows*cols], 1):
            scenario, result, path = self.load_scenario_and_result(scenario_id)
            
            if not scenario or not path:
                continue
            
            ax = fig.add_subplot(rows, cols, idx)
            
            # 経路プロット（XY平面）
            path_world = [self._grid_to_world(p) for p in path]
            path_x, path_y, path_z = zip(*path_world)
            ax.plot(path_x, path_y, 'b-', linewidth=2, alpha=0.8)
            
            # スタート・ゴール
            ax.scatter(scenario.start_position[0], scenario.start_position[1], 
                      c='green', s=100, marker='o')
            ax.scatter(scenario.goal_position[0], scenario.goal_position[1], 
                      c='red', s=100, marker='*')
            
            # タイトル
            title = f"#{scenario_id}: {scenario.terrain_params.terrain_type}"
            if result:
                title += f"\n{result.computation_time:.1f}s, {result.path_length:.1f}m"
            ax.set_title(title, fontsize=10)
            
            ax.set_xlabel('X (m)')
            ax.set_ylabel('Y (m)')
            ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # 保存
        output_file = self.output_dir / "path_comparison_multiple_2d.png"
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"✅ 2D比較図保存: {output_file}")
    
    def visualize_terrain_types_showcase(self):
        """地形タイプ別ショーケース（論文用）"""
        
        print("\n🎨 地形タイプ別ショーケース作成中...")
        
        # 各地形タイプから1つずつ選択
        terrain_types = [
            'flat_terrain',
            'gentle_slope', 
            'steep_slope',
            'mixed_terrain',
            'obstacle_field',
            'narrow_passage',
            'complex_3d'
        ]
        
        generator = ScenarioGenerator()
        scenarios = generator.load_scenarios("scenarios")
        
        selected_ids = []
        for terrain_type in terrain_types:
            scenario = next((s for s in scenarios if s.terrain_params.terrain_type == terrain_type), None)
            if scenario:
                selected_ids.append(scenario.scenario_id)
        
        # 7つを3x3グリッドで表示（2つ空白）
        self.visualize_multiple_paths(selected_ids, grid_layout=(3, 3))
        
        print("✅ 地形タイプショーケース完成")

def main():
    """メイン実行"""
    visualizer = PathVisualizer()
    
    print("🎨 経路可視化システム")
    print("=" * 60)
    
    # 例: シナリオ0の可視化
    print("\n1️⃣ 単一経路可視化（シナリオ0）")
    visualizer.visualize_single_path(0, show_obstacles=True)
    
    # 例: 最初の6シナリオの比較
    print("\n2️⃣ 複数経路比較（0-5）")
    visualizer.visualize_multiple_paths([0, 1, 2, 3, 4, 5], grid_layout=(2, 3))
    
    # 例: 地形タイプ別ショーケース
    print("\n3️⃣ 地形タイプ別ショーケース")
    visualizer.visualize_terrain_types_showcase()
    
    print("\n✅ 全ての可視化完了！")
    print(f"📂 出力先: {visualizer.output_dir}/")

if __name__ == "__main__":
    main()
