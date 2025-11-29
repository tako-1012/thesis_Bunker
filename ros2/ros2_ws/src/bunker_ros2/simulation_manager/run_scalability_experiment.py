#!/usr/bin/env python3
"""
スケーラビリティ実験

3つのスケールで全アルゴリズムを評価
"""
import json
import time
import numpy as np
from pathlib import Path
from typing import Dict, List
import sys

# パスを追加
sys.path.append('../path_planner_3d')

from astar_planner_3d_fixed import AStarPlanner3D
from weighted_astar_planner_3d import WeightedAStarPlanner3D
from terrain_aware_astar_planner_3d import TerrainAwareAStarPlanner3D
from dijkstra_planner_3d import DijkstraPlanner3D
from rrt_star_planner_3d import RRTStarPlanner3D

class ScalabilityExperiment:
    """スケーラビリティ実験"""
    
    def __init__(self):
        self.scales = ['small', 'medium', 'large']
        self.results = {}
    
    def run_experiment(self):
        """全スケールで実験実行"""
        for scale in self.scales:
            print(f"\n{'='*70}")
            print(f"{scale.upper()} SCALE 実験")
            print(f"{'='*70}")
            
            results = self._run_scale(scale)
            self.results[scale] = results
            
            # 中間結果を保存
            self._save_results()
    
    def _run_scale(self, scale):
        """1つのスケールで実験"""
        # スケール設定を取得
        from scalable_scenario_generator import ScalableScenarioGenerator
        config = ScalableScenarioGenerator.SCALES[scale]
        
        # アルゴリズムを初期化（スケールに応じたパラメータ）
        map_bounds = (
            list(config.min_bound),
            list(config.max_bound)
        )
        
        algorithms = {
            'Dijkstra': DijkstraPlanner3D(
                grid_size=(1,1,1),  # Dummy, will be recalculated
                voxel_size=config.voxel_size,
                map_bounds=map_bounds
            ),
            'A*': AStarPlanner3D(
                voxel_size=config.voxel_size,
                map_bounds=map_bounds
            ),
            'Weighted A*': WeightedAStarPlanner3D(
                grid_size=(1,1,1),  # Dummy, will be recalculated
                voxel_size=config.voxel_size,
                map_bounds=map_bounds
            ),
            'RRT*': RRTStarPlanner3D(
                grid_size=(1,1,1),  # Dummy, will be recalculated
                voxel_size=config.voxel_size,
                max_slope=30.0,
                map_bounds=map_bounds
            ),
            'TA-A* (Proposed)': TerrainAwareAStarPlanner3D(
                voxel_size=config.voxel_size,
                map_bounds=map_bounds
            )
        }
        
        # シナリオを読み込み
        scenario_dir = Path(f'../scenarios/scalability/{scale}_scale')
        scenario_files = sorted(scenario_dir.glob('scenario_*.json'))
        
        print(f"シナリオ数: {len(scenario_files)}")
        
        results = {algo: [] for algo in algorithms}
        
        # 各シナリオで実験
        for scenario_file in scenario_files:
            with open(scenario_file) as f:
                scenario = json.load(f)
            
            print(f"\nScenario {scenario['scenario_id']:03d} "
                  f"(distance: {scenario['distance']:.1f}m)")
            
            for algo_name, planner in algorithms.items():
                print(f"  {algo_name:20s}...", end=' ', flush=True)
                
                try:
                    start_time = time.time()
                    
                    # タイムアウトを自動設定
                    map_size = np.linalg.norm(np.array(config.max_bound) - np.array(config.min_bound))
                    if map_size < 30:  # Small
                        timeout = 600   # 10分
                    elif map_size < 80:  # Medium
                        timeout = 1800  # 30分
                    else:  # Large
                        timeout = 3600  # 60分
                    
                    if algo_name == 'A*':
                        result = planner.plan_path(
                            start=scenario['start'],
                            goal=scenario['goal']
                        )
                        success = result is not None
                        computation_time = planner.last_search_stats['computation_time']
                        path_length = planner.last_search_stats['path_length']
                        nodes_explored = planner.last_search_stats['nodes_explored']
                    else:
                        # 他のアルゴリズムはterrain_dataが必要
                        result = planner.plan_path(
                            start=scenario['start'],
                            goal=scenario['goal'],
                            terrain_data=np.zeros((100, 100, 20), dtype=int),  # 簡易地形
                            timeout=timeout
                        )
                        success = result.success
                        computation_time = result.computation_time
                        path_length = result.path_length
                        nodes_explored = result.nodes_explored
                    
                    elapsed = time.time() - start_time
                    
                    results[algo_name].append({
                        'scenario_id': scenario['scenario_id'],
                        'success': success,
                        'computation_time': computation_time,
                        'path_length': path_length if success else 0,
                        'nodes_explored': nodes_explored,
                        'distance': scenario['distance']
                    })
                    
                    status = "✅" if success else "❌"
                    print(f"{status} ({computation_time:.2f}s)")
                    
                except Exception as e:
                    print(f"❌ Error: {str(e)}")
                    results[algo_name].append({
                        'scenario_id': scenario['scenario_id'],
                        'success': False,
                        'error': str(e)
                    })
        
        return results
    
    def _save_results(self):
        """結果を保存"""
        output_path = Path('../results/scalability_results.json')
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\n結果を保存: {output_path}")
    
    def print_summary(self):
        """サマリーを表示"""
        print(f"\n{'='*70}")
        print("スケーラビリティ実験サマリー")
        print(f"{'='*70}")
        
        for scale in self.scales:
            if scale not in self.results:
                continue
            
            print(f"\n{scale.upper()} SCALE:")
            
            for algo, results in self.results[scale].items():
                success = sum(1 for r in results if r.get('success', False))
                total = len(results)
                rate = success / total * 100 if total > 0 else 0
                
                # 平均計算時間
                times = [r['computation_time'] for r in results if r.get('success', False)]
                avg_time = np.mean(times) if times else 0
                
                print(f"  {algo:20s}: {success:2d}/{total:2d} = {rate:5.1f}% "
                      f"(avg time: {avg_time:6.2f}s)")

if __name__ == '__main__':
    experiment = ScalabilityExperiment()
    experiment.run_experiment()
    experiment.print_summary()
