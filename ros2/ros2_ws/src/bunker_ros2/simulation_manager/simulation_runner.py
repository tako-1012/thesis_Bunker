#!/usr/bin/env python3
"""
simulation_runner.py
シミュレーション自動実行エンジン

機能:
- シナリオの自動実行
- path_planner_3dとの統合
- タイムアウト管理
- エラーハンドリング
- 進捗表示
"""

import sys
import time
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import json

# path_planner_3dをインポート
sys.path.insert(0, str(Path(__file__).parent.parent / 'path_planner_3d'))
from astar_planner_3d import AStarPlanner3D
from scenario_generator import Scenario, ScenarioGenerator

@dataclass
class SimulationResult:
    """シミュレーション実行結果"""
    scenario_id: int
    scenario_name: str
    success: bool
    path_found: bool
    path_length: float
    num_waypoints: int
    computation_time: float
    memory_usage: float
    cost_breakdown: Dict[str, float]
    error_message: str
    executed_at: str

class TerrainGenerator:
    """シナリオから地形グリッドを生成"""
    
    @staticmethod
    def generate_occupancy_grid(
        scenario: Scenario,
        grid_size: Tuple[int, int, int],
        voxel_size: float,
        min_bound: Tuple[float, float, float]
    ) -> np.ndarray:
        """障害物グリッド生成"""
        occupancy_grid = np.zeros(grid_size, dtype=np.uint8)
        terrain = scenario.terrain_params
        
        if terrain.terrain_type == 'flat_terrain':
            # 平地: ランダムな低密度障害物
            return TerrainGenerator._add_random_obstacles(
                occupancy_grid, terrain.obstacle_density
            )
        
        elif terrain.terrain_type == 'gentle_slope':
            # 緩斜面: 基本は空、一部に障害物
            return TerrainGenerator._add_random_obstacles(
                occupancy_grid, terrain.obstacle_density
            )
        
        elif terrain.terrain_type == 'steep_slope':
            # 急斜面: やや多めの障害物
            return TerrainGenerator._add_random_obstacles(
                occupancy_grid, terrain.obstacle_density
            )
        
        elif terrain.terrain_type == 'mixed_terrain':
            # 混合地形: 複数パターンの組み合わせ
            grid = TerrainGenerator._add_random_obstacles(
                occupancy_grid, terrain.obstacle_density * 0.5
            )
            grid = TerrainGenerator._add_block_obstacles(
                grid, count=5
            )
            return grid
        
        elif terrain.terrain_type == 'obstacle_field':
            # 障害物フィールド: 高密度障害物
            grid = TerrainGenerator._add_random_obstacles(
                occupancy_grid, terrain.obstacle_density * 0.6
            )
            grid = TerrainGenerator._add_block_obstacles(
                grid, count=10
            )
            return grid
        
        elif terrain.terrain_type == 'narrow_passage':
            # 狭い通路: 壁で囲まれた通路を作成
            return TerrainGenerator._create_narrow_passage(
                occupancy_grid, 
                passage_width=int(terrain.narrow_passage_width / voxel_size)
            )
        
        elif terrain.terrain_type == 'complex_3d':
            # 複雑3D: 多層障害物
            grid = TerrainGenerator._add_random_obstacles(
                occupancy_grid, terrain.obstacle_density * 0.4
            )
            grid = TerrainGenerator._add_multilayer_obstacles(
                grid, layers=3
            )
            return grid
        
        return occupancy_grid
    
    @staticmethod
    def generate_slope_grid(
        scenario: Scenario,
        grid_size: Tuple[int, int, int],
        voxel_size: float,
        min_bound: Tuple[float, float, float]
    ) -> np.ndarray:
        """勾配グリッド生成"""
        slope_grid = np.zeros(grid_size, dtype=np.float32)
        terrain = scenario.terrain_params
        
        if terrain.terrain_type in ['flat_terrain']:
            # 平地: ほぼ平坦（0-5度）
            slope_grid = np.random.uniform(0, 5, grid_size).astype(np.float32)
        
        elif terrain.terrain_type in ['gentle_slope']:
            # 緩斜面: 緩やかな勾配（5-20度）
            base_slope = np.linspace(5, 20, grid_size[0])
            for i in range(grid_size[0]):
                slope_grid[i, :, :] = base_slope[i] + np.random.uniform(-3, 3, (grid_size[1], grid_size[2]))
        
        elif terrain.terrain_type in ['steep_slope']:
            # 急斜面: 急な勾配（15-35度）
            base_slope = np.linspace(15, 35, grid_size[0])
            for i in range(grid_size[0]):
                slope_grid[i, :, :] = base_slope[i] + np.random.uniform(-5, 5, (grid_size[1], grid_size[2]))
        
        elif terrain.terrain_type in ['mixed_terrain', 'obstacle_field']:
            # 混合・障害物: 変動の大きい勾配
            slope_grid = np.random.uniform(0, terrain.max_slope, grid_size).astype(np.float32)
        
        elif terrain.terrain_type in ['narrow_passage']:
            # 狭い通路: 中程度の勾配
            slope_grid = np.random.uniform(5, 20, grid_size).astype(np.float32)
        
        elif terrain.terrain_type in ['complex_3d']:
            # 複雑3D: 高い変動性
            slope_grid = np.random.uniform(0, terrain.max_slope, grid_size).astype(np.float32)
            # ノイズ追加
            slope_grid += np.random.normal(0, 5, grid_size).astype(np.float32)
            slope_grid = np.clip(slope_grid, 0, terrain.max_slope)
        
        # 粗さを反映
        if terrain.roughness > 0.3:
            noise = np.random.normal(0, terrain.roughness * 10, grid_size)
            slope_grid += noise.astype(np.float32)
            slope_grid = np.clip(slope_grid, 0, 60)
        
        return slope_grid
    
    @staticmethod
    def _add_random_obstacles(grid: np.ndarray, density: float) -> np.ndarray:
        """ランダム障害物追加"""
        mask = np.random.random(grid.shape) < density
        grid[mask] = 1
        return grid
    
    @staticmethod
    def _add_block_obstacles(grid: np.ndarray, count: int) -> np.ndarray:
        """ブロック状障害物追加"""
        for _ in range(count):
            x = np.random.randint(10, grid.shape[0] - 10)
            y = np.random.randint(10, grid.shape[1] - 10)
            z = np.random.randint(0, grid.shape[2] - 5)
            
            size_x = np.random.randint(3, 8)
            size_y = np.random.randint(3, 8)
            size_z = np.random.randint(2, 5)
            
            grid[x:x+size_x, y:y+size_y, z:z+size_z] = 1
        
        return grid
    
    @staticmethod
    def _create_narrow_passage(grid: np.ndarray, passage_width: int) -> np.ndarray:
        """狭い通路作成"""
        # 両側に壁を作成
        grid[:, :passage_width//2, :] = 1
        grid[:, -passage_width//2:, :] = 1
        
        # ランダムな障害物を通路内に配置
        center = grid.shape[1] // 2
        for _ in range(5):
            x = np.random.randint(10, grid.shape[0] - 10)
            grid[x:x+5, center-passage_width//4:center+passage_width//4, 0:2] = 1
        
        return grid
    
    @staticmethod
    def _add_multilayer_obstacles(grid: np.ndarray, layers: int) -> np.ndarray:
        """多層障害物追加"""
        z_step = grid.shape[2] // layers
        for layer in range(layers):
            z_start = layer * z_step
            z_end = min((layer + 1) * z_step, grid.shape[2])
            
            # 各層にランダム障害物
            mask = np.random.random(grid[:, :, z_start:z_end].shape) < 0.15
            grid[:, :, z_start:z_end][mask] = 1
        
        return grid

class SimulationRunner:
    """シミュレーション実行エンジン"""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or self._default_config()
        self.results: List[SimulationResult] = []
        
        # path_planner_3dの設定
        self.grid_size = tuple(self.config['grid_size'])
        self.voxel_size = self.config['voxel_size']
        self.min_bound = tuple(self.config['min_bound'])
        
        # プランナー初期化
        self.planner = AStarPlanner3D(
            voxel_size=self.voxel_size,
            grid_size=self.grid_size,
            min_bound=self.min_bound
        )
        
        print("🤖 SimulationRunner初期化完了")
        print(f"  グリッドサイズ: {self.grid_size}")
        print(f"  ボクセルサイズ: {self.voxel_size}m")
    
    def _default_config(self) -> Dict:
        """デフォルト設定"""
        return {
            'grid_size': [100, 100, 30],
            'voxel_size': 0.1,
            'min_bound': [-5.0, -5.0, 0.0],
            'max_bound': [5.0, 5.0, 3.0],  # 追加
            'timeout': 30.0,  # 30秒タイムアウト
            'max_iterations': 100000
        }
    
    def run_scenario(self, scenario: Scenario) -> SimulationResult:
        """単一シナリオ実行"""
        print(f"\n🚀 シナリオ実行: {scenario.name} ({scenario.expected_difficulty})")
        
        start_time = time.time()
        
        try:
            # 地形生成
            print("  📊 地形生成中...")
            occupancy_grid = TerrainGenerator.generate_occupancy_grid(
                scenario, self.grid_size, self.voxel_size, self.min_bound
            )
            slope_grid = TerrainGenerator.generate_slope_grid(
                scenario, self.grid_size, self.voxel_size, self.min_bound
            )
            
            # スタート・ゴールをグリッド座標に変換
            start_grid = self._world_to_grid(scenario.start_position)
            goal_grid = self._world_to_grid(scenario.goal_position)
            
            print(f"  📍 Start: {start_grid}, Goal: {goal_grid}")
            
            # スタート・ゴールが障害物でないことを確認
            if occupancy_grid[start_grid] == 1:
                print("  ⚠️ スタート地点が障害物です")
                occupancy_grid[start_grid] = 0
            
            if occupancy_grid[goal_grid] == 1:
                print("  ⚠️ ゴール地点が障害物です")
                occupancy_grid[goal_grid] = 0
            
            # 経路計画実行
            print("  🔍 経路計画実行中...")
            plan_start = time.time()
            
            # ワールド座標で経路計画実行
            path = self.planner.plan_path(
                scenario.start_position,
                scenario.goal_position
            )
            
            computation_time = time.time() - plan_start
            
            # 結果評価
            if path and len(path) > 0:
                path_length = self._calculate_path_length(path)
                print(f"  ✅ 経路発見: {len(path)}ウェイポイント, 長さ{path_length:.2f}m, {computation_time:.4f}秒")
                
                result = SimulationResult(
                    scenario_id=scenario.scenario_id,
                    scenario_name=scenario.name,
                    success=True,
                    path_found=True,
                    path_length=path_length,
                    num_waypoints=len(path),
                    computation_time=computation_time,
                    memory_usage=0.0,  # TODO: 実装
                    cost_breakdown={},  # TODO: 実装
                    error_message="",
                    executed_at=datetime.now().isoformat()
                )
            else:
                print(f"  ❌ 経路が見つかりません: {computation_time:.4f}秒")
                result = SimulationResult(
                    scenario_id=scenario.scenario_id,
                    scenario_name=scenario.name,
                    success=False,
                    path_found=False,
                    path_length=0.0,
                    num_waypoints=0,
                    computation_time=computation_time,
                    memory_usage=0.0,
                    cost_breakdown={},
                    error_message="No path found",
                    executed_at=datetime.now().isoformat()
                )
        
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"  ❌ エラー発生: {str(e)}")
            result = SimulationResult(
                scenario_id=scenario.scenario_id,
                scenario_name=scenario.name,
                success=False,
                path_found=False,
                path_length=0.0,
                num_waypoints=0,
                computation_time=elapsed,
                memory_usage=0.0,
                cost_breakdown={},
                error_message=str(e),
                executed_at=datetime.now().isoformat()
            )
        
        self.results.append(result)
        return result
    
    def run_all_scenarios(
        self, 
        scenarios: List[Scenario],
        save_interval: int = 10
    ) -> List[SimulationResult]:
        """全シナリオ実行"""
        total = len(scenarios)
        print(f"\n{'='*60}")
        print(f"🚀 大規模シミュレーション開始: {total}シナリオ")
        print(f"{'='*60}\n")
        
        overall_start = time.time()
        
        for i, scenario in enumerate(scenarios, 1):
            print(f"\n[{i}/{total}] ", end='')
            result = self.run_scenario(scenario)
            
            # 進捗表示
            if i % save_interval == 0:
                self._save_intermediate_results(i)
                self._print_progress_summary(i, total)
        
        overall_time = time.time() - overall_start
        
        print(f"\n{'='*60}")
        print(f"✅ 大規模シミュレーション完了!")
        print(f"  総実行時間: {overall_time:.2f}秒 ({overall_time/60:.1f}分)")
        print(f"  成功率: {self._calculate_success_rate():.1f}%")
        print(f"{'='*60}\n")
        
        return self.results
    
    def _world_to_grid(self, world_pos: Tuple[float, float, float]) -> Tuple[int, int, int]:
        """ワールド座標→グリッド座標変換"""
        x = int((world_pos[0] - self.min_bound[0]) / self.voxel_size)
        y = int((world_pos[1] - self.min_bound[1]) / self.voxel_size)
        z = int((world_pos[2] - self.min_bound[2]) / self.voxel_size)
        
        # グリッド範囲内にクリップ
        x = max(0, min(x, self.grid_size[0] - 1))
        y = max(0, min(y, self.grid_size[1] - 1))
        z = max(0, min(z, self.grid_size[2] - 1))
        
        return (x, y, z)
    
    def _calculate_path_length(self, path: List[Tuple[float, float, float]]) -> float:
        """経路長計算"""
        if len(path) < 2:
            return 0.0
        
        length = 0.0
        for i in range(len(path) - 1):
            p1 = np.array(path[i])
            p2 = np.array(path[i+1])
            length += np.linalg.norm(p2 - p1)
        
        return length
    
    def _calculate_success_rate(self) -> float:
        """成功率計算"""
        if not self.results:
            return 0.0
        successful = sum(1 for r in self.results if r.path_found)
        return (successful / len(self.results)) * 100
    
    def _print_progress_summary(self, current: int, total: int):
        """進捗サマリー表示"""
        success_rate = self._calculate_success_rate()
        avg_time = np.mean([r.computation_time for r in self.results])
        
        print(f"\n  📊 中間進捗 ({current}/{total}):")
        print(f"    成功率: {success_rate:.1f}%")
        print(f"    平均計算時間: {avg_time:.4f}秒")
    
    def _save_intermediate_results(self, count: int):
        """中間結果保存"""
        output_dir = Path("simulation_manager/results")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_file = output_dir / f"intermediate_results_{count:03d}.json"
        with open(output_file, 'w') as f:
            json.dump([asdict(r) for r in self.results], f, indent=2)
    
    def save_results(self, output_path: str = "simulation_manager/results/final_results.json"):
        """最終結果保存"""
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w') as f:
            json.dump([asdict(r) for r in self.results], f, indent=2)
        
        print(f"💾 結果保存完了: {output_file}")

def main():
    """メイン実行"""
    # シナリオ読み込み
    generator = ScenarioGenerator()
    scenarios = generator.load_scenarios("simulation_manager/scenarios")
    
    print(f"📂 {len(scenarios)}個のシナリオを読み込みました")
    
    # シミュレーション実行
    runner = SimulationRunner()
    results = runner.run_all_scenarios(scenarios, save_interval=10)
    
    # 結果保存
    runner.save_results()
    
    print("\n🎉 全てのシミュレーション完了!")

if __name__ == "__main__":
    main()
